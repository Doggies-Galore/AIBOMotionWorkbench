# Huge thanks to Dogsbody for giving me some handy file format info!
# Snippets of this applet were developed with an LLM
# Made with <3 by Doggies Galore

import struct
import json

# Define constants based on the updated specifications
SIGNATURE = b"OMTN"

# Format strings for parsing Block0, the header, and keyframes
BLOCK0_FORMAT = "<IIIHHHHI"
BLOCK_HEADER_FORMAT = "<II"
KEYFRAME_HEADER_FORMAT = "<HHII"

# DRX to ERS model mapping
PLATFORM_MAP = {
    "DRX-700": "ERS-110",
    "DRX-910": "ERS-210",
    "DRX-900": "ERS-220",
    "DRX-801": "ERS-310",
    "DRX-1000": "ERS-7"
}

PoseNameLookup = {
    0: "Sleep",
    1: "Sit",
    2: "Stand"
}

# joint PRM to movement names are stored in a JSON dict.
with open('joints.json', 'r') as f:
    JOINTS_MAP = json.load(f)

def read_variable_length_string(f):
    length_byte = struct.unpack("B", f.read(1))[0]
    return f.read(length_byte).decode("utf-8", errors='ignore')

def parse_chunk_name(chunk_name):
    parts = chunk_name.split("#")
    if len(parts) != 2:
        return "Unknown format"

    usage = {
        "a": "All servos",
        "h": "Head servos only",
        "l": "Leg servos only",
        "m": "Mouth servo only",
        "e": "Ear servos only",
        "t": "Tail servos only"
    }.get(parts[0][0], "Unknown - servo use not specified")

    skit_title = parts[1].split('_', 1)[1].replace('_', ' ')

    action_posture = f"{parts[0][2:].capitalize()} -> {parts[1].split('_')[0].capitalize()}"

    return f"Uses: {usage}\n  Action Posture: {action_posture}\n  Action Title: {skit_title}"

def parse_format_platform(format_platform):
    return PLATFORM_MAP.get(format_platform, format_platform)

def parse_mtn_file(filename):
    with open(filename, "rb") as f:
        # Read and verify the signature
        signature = f.read(4)
        if signature != SIGNATURE:
            print("File format warning: Signature mismatch. Some AIBOWare may have different headers. If you know what you're doing, you can safely disregard.")

        # Read block 0
        block0_header = f.read(struct.calcsize(BLOCK0_FORMAT))
        block_num, block_size, num_sections, major_ver, minor_ver, tile_count, frame_rate, options = struct.unpack(BLOCK0_FORMAT, block0_header)

        print(f"MTN Block 0:")
        print(f"  Block Number: {block_num}")
        print(f"  Block Size: {block_size}")
        print(f"  Number of Sections: {num_sections}")
        print(f"  Version: {major_ver}.{minor_ver}")
        print(f"  Keyframe Count: {tile_count}")
        print(f"  Frame Rate (msec/frame): {frame_rate}")
        print(f"  Options: {options}")

        # Parse subsequent blocks
        current_offset = f.tell()
        for block_index in range(1, num_sections):
            # Read the block header
            block_header = f.read(struct.calcsize(BLOCK_HEADER_FORMAT))
            if not block_header:
                break
            block_num, block_len = struct.unpack(BLOCK_HEADER_FORMAT, block_header)

            print(f"\nMTN Block {block_num}:")
            print(f"  Block Length: {block_len}")

            if block_index == 1:
                # Read and decode variable-length strings for file authoring and AIBO model information
                action_chunk_name = read_variable_length_string(f)
                author_name = read_variable_length_string(f)
                format_name = read_variable_length_string(f)
                ers_format_name = parse_format_platform(format_name)

                print(f"Action information:")
                print(parse_chunk_name(action_chunk_name))
                print(f"  Author/Utility name: {author_name}")
                print(f"  Format (aibo-platform): {ers_format_name}")

            elif block_index == 2:
                # Read servo count and get joints in action
                num_joints = struct.unpack("<H", f.read(2))[0]
                print(f"  Number of Joints: {num_joints}")

                prm_codes = []
                print("  Servo PRM Joint Names:")
                for _ in range(num_joints):
                    prm_code = "PRM:" + read_variable_length_string(f).split("PRM:")[1]
                    prm_codes.append(prm_code)
                    print(f"    PRM Code: {prm_code}")

                    # Match PRM code to joint name using joints.json for the correct platform
                    if ers_format_name in JOINTS_MAP and prm_code in JOINTS_MAP[ers_format_name]:
                        joint_name = JOINTS_MAP[ers_format_name][prm_code]
                        print(f"    Joint Name: {joint_name}")
                    else:
                        print(f"    Joint Name: Not found in joints.json for {ers_format_name}")

            elif block_index > 2:
                print(f"\nMTN Block {block_num}:")
                print(f"  Block Length: {block_len}")

                # Read keyframes
                keyframes = []
                for keyframe_index in range(tile_count):
                    keyframe_header = f.read(struct.calcsize(KEYFRAME_HEADER_FORMAT))
                    if not keyframe_header:
                        break
                    time_delta, dummy1, dummy2, dummy3 = struct.unpack(KEYFRAME_HEADER_FORMAT, keyframe_header)

                    keyframe_positions = []
                    for joint_index in range(num_joints):
                        angle_uradians = struct.unpack("<i", f.read(4))[0]
                        angle_degrees = angle_uradians * 180.0 / (1000000.0 * 3.141592654)
                        joint_name = JOINTS_MAP[ers_format_name].get(prm_codes[joint_index], f"Unknown joint {joint_index + 1}")
                        keyframe_positions.append({
                            "JointName": joint_name,
                            "Angle_urad": angle_uradians,
                            "Angle_degrees": angle_degrees
                        })

                    keyframes.append(keyframe_positions)

                json_filename = f"./poses/{ers_format_name}.json"
                with open(json_filename, 'r') as json_file:
                    json_data = json.load(json_file)

                    # Get all poses from JSON
                    poses = json_data["Poses"]

                    for pose_idx, pose_data in enumerate(poses):
                        expected_positions = pose_data["JointPositions"]
                        matching_keyframes = []

                        for kf_idx, kf_positions in enumerate(keyframes):
                            keyframe_matching = True
                            for pos1, pos2 in zip(kf_positions, expected_positions):
                                if pos1["Angle_degrees"] != pos2["Angle_degrees"]:
                                    if abs(pos1["Angle_degrees"] - pos2["Angle_degrees"]) > 5:
                                        keyframe_matching = False
                                        break
                            if keyframe_matching:
                                matching_keyframes.append(kf_idx)

                        if matching_keyframes:
                            print(f"Pose {PoseNameLookup[pose_idx]} matched in keyframes: {matching_keyframes}")

                        # Print result for this pose
                        for kf_idx in matching_keyframes:
                            print(f"Pose {PoseNameLookup[pose_idx]} matched in keyframe {kf_idx}:")
                            print("The standard " + PoseNameLookup[pose_idx] + " pose for " + ers_format_name + " was found.")

            # Move file pointer to the start of the next block
            current_offset += block_len
            f.seek(current_offset)

if __name__ == "__main__":
    filename = "S2S.mtn"
    print("Opening and running processing for " + filename)
    parse_mtn_file(filename)
    print("Finished.")
