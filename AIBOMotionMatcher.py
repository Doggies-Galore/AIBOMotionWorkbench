#This script is still in progress.
#Snippets of this applet were developed with an LLM

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

# ERS to DRX model mapping
DRX_MODEL_MAP = {v: k for k, v in PLATFORM_MAP.items()}

# Load joint PRM to movement names mapping from JSON
with open('joints.json', 'r') as f:
    JOINTS_MAP = json.load(f)

# Load conversion of movements from ERS to ERS.
with open('conversion.json', 'r') as f:
    CONVERSION_MAP = json.load(f)

def read_variable_length_string(f):
    length_byte = struct.unpack("B", f.read(1))[0]
    return f.read(length_byte).decode("utf-8", errors='ignore')

def parse_format_platform(format_platform):
    return PLATFORM_MAP.get(format_platform, format_platform)

def parse_drx_model(ers_model):
    return DRX_MODEL_MAP.get(ers_model, ers_model)

def pad_to_dword_offset(fw, current_offset):
    padding_needed = (4 - (current_offset % 4)) % 4
    if padding_needed > 0:
        fw.write(b'\x00' * padding_needed)
    return current_offset + padding_needed

def extract_and_save_joint_positions(f, fw, num_joints, frame_rate, ers_format_name, prm_codes, tile_count, target_ers_model):
    # Load poses for the recognized model
    source_poses_filename = f"./poses/{ers_format_name}.json"
    target_poses_filename = f"./poses/{target_ers_model}.json"

    with open(source_poses_filename, 'r') as source_poses_file:
        source_poses = json.load(source_poses_file)["Poses"]

    with open(target_poses_filename, 'r') as target_poses_file:
        target_poses = json.load(target_poses_file)["Poses"]

    print("  Keyframes:")
    keyframes = []
    for keyframe_index in range(tile_count):
        keyframe_header = f.read(struct.calcsize(KEYFRAME_HEADER_FORMAT))
        if not keyframe_header:
            break
        time_delta, dummy1, dummy2, dummy3 = struct.unpack(KEYFRAME_HEADER_FORMAT, keyframe_header)

        time_msecs = (time_delta + 1) * frame_rate
        print(f"  Keyframe {keyframe_index + 1}:")
        print(f"    Time Delta: {time_delta}, Elapsed Time (msec): {time_msecs}")

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
        fw.write(keyframe_header)

        # Check for matching pose
        matching_pose = None
        for pose in source_poses:
            match = True
            for jp, kp in zip(pose["JointPositions"], keyframe_positions):
                if abs(jp["Angle_degrees"] - kp["Angle_degrees"]) > 5:
                    match = False
                    break
            if match:
                matching_pose = pose
                break

        if matching_pose:
            # Replace with the target model's pose
            pose_index = source_poses.index(matching_pose)
            target_pose = target_poses[pose_index]["JointPositions"]
            print(f"Replacing keyframe {keyframe_index + 1} with pose {pose_index} from {target_ers_model}")
            for joint_index, target_joint in enumerate(target_pose):
                if joint_index < num_joints:  # Only replace the existing joints
                    angle_uradians = int(target_joint["Angle_urad"])
                    fw.write(struct.pack("<i", angle_uradians))
                else:
                    break  # Stop if the target model has more joints than the original model
        else:
            # Write original angles if no matching pose is found
            for joint_position in keyframe_positions:
                fw.write(struct.pack("<i", joint_position["Angle_urad"]))


def convert_mtn_file(filename, target_ers_model):
    with open(filename, "rb") as f:
        signature = f.read(4)
        if signature != SIGNATURE:
            print("File format warning: Signature mismatch.")

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

        new_filename = filename.replace('.mtn', '_converted.mtn')
        with open(new_filename, "wb") as fw:
            fw.write(signature)
            fw.write(block0_header)

            current_offset = f.tell()
            for block_index in range(1, num_sections):
                current_offset = pad_to_dword_offset(fw, current_offset)
                fw.seek(current_offset)

                block_header = f.read(struct.calcsize(BLOCK_HEADER_FORMAT))
                if not block_header:
                    break
                block_num, block_len = struct.unpack(BLOCK_HEADER_FORMAT, block_header)
                fw.write(block_header)

                if block_index == 1:
                    action_chunk_name = read_variable_length_string(f)
                    author_name = read_variable_length_string(f)
                    format_name_length = struct.unpack("B", f.read(1))[0]
                    format_name = f.read(format_name_length).decode()

                    drx_model = parse_drx_model(target_ers_model)

                    fw.write(len(action_chunk_name).to_bytes(1, 'little'))
                    fw.write(action_chunk_name.encode())
                    fw.write(len(author_name).to_bytes(1, 'little'))
                    fw.write(author_name.encode())
                    fw.write(len(drx_model).to_bytes(1, 'little'))
                    fw.write(drx_model.encode())

                elif block_index == 2:
                    num_joints = struct.unpack("<H", f.read(2))[0]
                    fw.write(struct.pack("<H", num_joints))

                    prm_codes = []
                    for _ in range(num_joints):
                        prm_code_length = struct.unpack("B", f.read(1))[0]
                        prm_code = f.read(prm_code_length).decode()
                        prm_codes.append(prm_code)

                        if parse_format_platform(format_name) in JOINTS_MAP and prm_code in JOINTS_MAP[parse_format_platform(format_name)]:
                            movement_name = JOINTS_MAP[parse_format_platform(format_name)][prm_code]
                        else:
                            movement_name = prm_code

                        if movement_name in CONVERSION_MAP and target_ers_model in CONVERSION_MAP[movement_name]:
                            target_prm_code = CONVERSION_MAP[movement_name][target_ers_model]
                        else:
                            target_prm_code = prm_code

                        fw.write(len(target_prm_code).to_bytes(1, 'little'))
                        fw.write(target_prm_code.encode())

                elif block_index == 3:
                    extract_and_save_joint_positions(f, fw, num_joints, frame_rate, parse_format_platform(format_name), prm_codes, tile_count, target_ers_model)

                current_offset += block_len
                f.seek(current_offset)

        print(f"Conversion completed. Converted file saved as: {new_filename}")


if __name__ == "__main__":
    filename = "S2S.mtn"  # Replace with your MTN file name
    target_ers_model = input("Enter the target ERS model (e.g., ERS-7): ").strip()
    
    if target_ers_model not in PLATFORM_MAP.values():
        print(f"Unsupported ERS model: {target_ers_model}. Supported models: {list(PLATFORM_MAP.values())}")
    else:
        print(f"Opening and converting {filename} to {target_ers_model}...")
        convert_mtn_file(filename, target_ers_model)
        print("Conversion finished.")
