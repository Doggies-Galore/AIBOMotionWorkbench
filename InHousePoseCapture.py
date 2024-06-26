#Huge thanks to Dogsbody for helping me with some handy file format info!
#Snippets of this applet were developed with an LLM
#Made with <3 by Doggies Galore

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

# joint PRM to movement names are stored in a JSON dict.
with open('joints.json', 'r') as f:
    JOINTS_MAP = json.load(f)

def read_variable_length_string(f):
    length_byte = struct.unpack("B", f.read(1))[0]
    #In mtn files, there is some hex that can be interpreted as broken UTF-8, so we'll ignore it here.
    return f.read(length_byte).decode("utf-8", errors='ignore')

def save_poses_to_json(filename, poses):
    poses_data = {
        "Poses": poses
    }
    with open(filename, 'w') as json_file:
        json.dump(poses_data, json_file, indent=4)
    print(f"Saved poses to {filename}")

    
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
        signature = f.read(4)
        if signature != SIGNATURE:
            print("File format warning: Signature mismatch. Some AIBOWare may have different headers. If you know what you're doing, you can safely disregard.")

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

        current_offset = f.tell()
        poses = []

        for block_index in range(1, num_sections):
            block_header = f.read(struct.calcsize(BLOCK_HEADER_FORMAT))
            if not block_header:
                break
            block_num, block_len = struct.unpack(BLOCK_HEADER_FORMAT, block_header)

            print(f"\nMTN Block {block_num}:")
            print(f"  Block Length: {block_len}")

            if block_index == 1:
                action_chunk_name = read_variable_length_string(f)
                author_name = read_variable_length_string(f)
                format_name = read_variable_length_string(f)
                ers_format_name = parse_format_platform(format_name)

                print(f"Action information:")
                print(parse_chunk_name(action_chunk_name))
                print(f"  Author/Utility name: {author_name}")
                print(f"  Format (aibo-platform): {ers_format_name}")

            elif block_index == 2:
                num_joints = struct.unpack("<H", f.read(2))[0]
                print(f"  Number of Joints: {num_joints}")

                prm_codes = []
                print("  Servo PRM Joint Names:")
                for _ in range(num_joints):
                    prm_code = "PRM:" + read_variable_length_string(f).split("PRM:")[1]
                    prm_codes.append(prm_code)
                    print(f"    PRM Code: {prm_code}")

                    if ers_format_name in JOINTS_MAP and prm_code in JOINTS_MAP[ers_format_name]:
                        joint_name = JOINTS_MAP[ers_format_name][prm_code]
                        print(f"    Joint Name: {joint_name}")
                    else:
                        print(f"    Joint Name: Not found in joints.json for {ers_format_name}")

            elif block_index == 3:
                print("  Keyframes:")
                for keyframe_index in range(tile_count):
                    keyframe_header = f.read(struct.calcsize(KEYFRAME_HEADER_FORMAT))
                    if not keyframe_header:
                        break
                    time_delta, dummy1, dummy2, dummy3 = struct.unpack(KEYFRAME_HEADER_FORMAT, keyframe_header)
                    
                    time_msecs = (time_delta + 1) * frame_rate
                    joint_positions = []
                    for joint_index in range(num_joints):
                        angle_uradians = struct.unpack("<i", f.read(4))[0]
                        angle_degrees = angle_uradians * 180.0 / (1000000.0 * 3.141592654)
                        joint_name = JOINTS_MAP[ers_format_name].get(prm_codes[joint_index], f"Unknown joint {joint_index + 1}")
                        joint_data = {
                            "JointName": joint_name,
                            "Angle_urad": angle_uradians,
                            "Angle_degrees": angle_degrees
                        }
                        joint_positions.append(joint_data)

                    # Add formatted pose data
                    pose_name = ""
                    if keyframe_index == 0:
                        pose_name = "Sleep"
                    elif keyframe_index == 1:
                        pose_name = "Sit"
                    elif keyframe_index == 2:
                        pose_name = "Stand"
                    
                    pose_data = {
                        "Pose": pose_name,
                        "JointPositions": joint_positions
                    }
                    poses.append(pose_data)
                    print(f"    Saved pose '{pose_name}' from keyframe {keyframe_index + 1}")

            current_offset += block_len
            f.seek(current_offset)
        filename = filename.split(".")[0]
        # Save all poses to a JSON file
        save_poses_to_json(filename +".json", poses)


if __name__ == "__main__":
    filename = "7.mtn" 
    print("Opening and saving positions for " + filename)
    parse_mtn_file(filename)
    print("Finished.")