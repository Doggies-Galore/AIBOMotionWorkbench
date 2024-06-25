#This script is still in progress.
#Snippets of this applet were developed with an LLM
#This script only changes the DRX model header so that applications like Skitter will accept it.

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

def convert_mtn_file(filename, target_ers_model):
    with open(filename, "rb") as f:
        # Read and verify the signature
        signature = f.read(4)
        if signature != SIGNATURE:
            print("File format warning: Signature mismatch.")

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

        # Prepare to write to a new MTN file
        new_filename = filename.replace('.mtn', '_converted.mtn')
        with open(new_filename, "wb") as fw:
            # Write the original signature and block 0
            fw.write(signature)
            fw.write(block0_header)

            # Parse subsequent blocks
            current_offset = f.tell()
            for block_index in range(1, num_sections):
                # Pad to DWORD offset
                current_offset = pad_to_dword_offset(fw, current_offset)
                fw.seek(current_offset)

                # Read the block header
                block_header = f.read(struct.calcsize(BLOCK_HEADER_FORMAT))
                if not block_header:
                    break
                block_num, block_len = struct.unpack(BLOCK_HEADER_FORMAT, block_header)

                # Write the block header to the new file
                fw.write(block_header)

                if block_index == 1:
                    # Read and write variable-length strings for file authoring and AIBO model information
                    action_chunk_name = read_variable_length_string(f)
                    author_name = read_variable_length_string(f)
                    format_name_length = struct.unpack("B", f.read(1))[0]
                    format_name = f.read(format_name_length).decode()

                    # Convert ERS model to DRX model for the header
                    drx_model = parse_drx_model(target_ers_model)

                    # Write original variable-length strings to the new file
                    fw.write(len(action_chunk_name).to_bytes(1, 'little'))
                    fw.write(action_chunk_name.encode())
                    fw.write(len(author_name).to_bytes(1, 'little'))
                    fw.write(author_name.encode())
                    fw.write(len(drx_model).to_bytes(1, 'little'))
                    fw.write(drx_model.encode())

                elif block_index == 2:
                    # Read servo count
                    num_joints = struct.unpack("<H", f.read(2))[0]

                    # Write servo count to the new file
                    fw.write(struct.pack("<H", num_joints))

                    # Read and replace PRM codes with movement names
                    for _ in range(num_joints):
                        prm_code_length = struct.unpack("B", f.read(1))[0]
                        prm_code = f.read(prm_code_length).decode()

                        # Determine movement name based on current ERS model
                        if parse_format_platform(format_name) in JOINTS_MAP and prm_code in JOINTS_MAP[parse_format_platform(format_name)]:
                            movement_name = JOINTS_MAP[parse_format_platform(format_name)][prm_code]
                        else:
                            movement_name = prm_code  # fallback to original if not found

                        # Determine PRM code for target ERS model
                        if movement_name in CONVERSION_MAP and target_ers_model in CONVERSION_MAP[movement_name]:
                            target_prm_code = CONVERSION_MAP[movement_name][target_ers_model]
                        else:
                            target_prm_code = prm_code  # fallback to original if not found

                        # Write modified PRM code to the new file
                        fw.write(len(target_prm_code).to_bytes(1, 'little'))
                        fw.write(target_prm_code.encode())

                elif block_index == 3:
                    # Copy keyframe data as is
                    keyframe_data = f.read(block_len)
                    fw.write(keyframe_data)

                # Move file pointer to the start of the next block
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
