"""
IP Room Effect Image Generation Script

Usage (完整流程):
    python generate.py \
        --room-images /path/to/room1.jpg /path/to/room2.jpg \
        --ip-name ultraman \
        --room-region suite_bedroom \
        --material-types carpet painting pillow bedspread curtain \
        --output-dir /mnt/user-data/outputs/ip-room/

Usage (仅生成提示词):
    python generate.py \
        --room-images /path/to/room1.jpg /path/to/room2.jpg \
        --ip-name ultraman \
        --room-region suite_bedroom \
        --output-dir /mnt/user-data/outputs/ip-room/ \
        --prompt-only

Usage (使用已有提示词生图):
    python generate.py \
        --room-images /path/to/room1.jpg /path/to/room2.jpg \
        --ip-name ultraman \
        --room-region suite_bedroom \
        --output-dir /mnt/user-data/outputs/ip-room/ \
        --prompt-file /mnt/user-data/outputs/ip-room/prompt.json
"""

import base64
import json
import os
import sys
from pathlib import Path

import httpx

API_BASE = os.environ.get("STOCK_API_BASE_URL", "http://localhost:8000")


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def list_materials(ip_name: str, room_region: str | None = None) -> list[dict]:
    params = {"ip_name": ip_name}
    if room_region:
        params["room_region"] = room_region
    resp = httpx.get(f"{API_BASE}/api/ip-room/materials", params=params)
    resp.raise_for_status()
    data = resp.json()
    if data["code"] != 200:
        print(f"Error listing materials: {data['message']}")
        sys.exit(1)
    return data["data"]


def call_generate_prompt(
    ip_name: str,
    room_region: str,
    room_images_b64: list[str],
    material_types: list[str],
    style_note: str | None,
) -> dict:
    payload = {
        "ip_name": ip_name,
        "room_region": room_region,
        "room_images": room_images_b64,
        "material_types": material_types,
    }
    if style_note:
        payload["style_note"] = style_note

    resp = httpx.post(f"{API_BASE}/api/ip-room/generate-prompt", json=payload, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    if data["code"] != 200:
        print(f"Error generating prompt: {data['message']}")
        sys.exit(1)
    return data["data"]


def call_generate_images(
    prompt: str,
    negative_prompt: str | None,
    room_images_b64: list[str],
    max_images: int = 4,
    output_dir: str = "./outputs",
) -> list[str]:
    payload = {
        "prompt": prompt,
        "room_images": room_images_b64,
        "size": "2K",
        "max_images": max_images,
        "sequential": True,
        "watermark": False,
        "response_format": "url",
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    resp = httpx.post(f"{API_BASE}/api/ip-room/generate-image", json=payload, timeout=600)
    resp.raise_for_status()
    data = resp.json()
    if data["code"] != 200:
        print(f"Error generating images: {data['message']}")
        sys.exit(1)

    images = data["data"]["images"]
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for i, img in enumerate(images):
        if "url" in img:
            img_resp = httpx.get(img["url"], timeout=120)
            img_resp.raise_for_status()
            file_name = f"ip_room_{i+1:02d}.jpg"
            file_path = output_path / file_name
            with open(file_path, "wb") as f:
                f.write(img_resp.content)
            saved_paths.append(str(file_path))
            print(f"Saved image {i+1}: {file_path}")
        elif "b64_json" in img:
            file_name = f"ip_room_{i+1:02d}.jpg"
            file_path = output_path / file_name
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(img["b64_json"]))
            saved_paths.append(str(file_path))
            print(f"Saved image {i+1}: {file_path}")

    usage = data["data"].get("usage", {})
    print(f"Generated {usage.get('generated_images', len(saved_paths))} images, tokens: {usage.get('output_tokens', 0)}")
    return saved_paths


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate IP Room Effect Images")
    parser.add_argument("--room-images", nargs="+", required=True, help="房间原图文件路径（多角度）")
    parser.add_argument("--ip-name", required=True, help="IP 名称")
    parser.add_argument("--room-region", required=True, help="房间区域: suite_living_room, suite_bedroom, standard_bedroom, single_bedroom, bathroom")
    parser.add_argument("--material-types", nargs="+", default=["carpet", "painting", "pillow", "bedspread", "curtain"], help="要添加的物料类型")
    parser.add_argument("--style-note", default=None, help="风格说明")
    parser.add_argument("--output-dir", default="./outputs", help="效果图输出目录")
    parser.add_argument("--max-images", type=int, default=4, help="最多生成图片数 (1-15)")
    parser.add_argument("--prompt-only", action="store_true", help="仅生成提示词，不生图")
    parser.add_argument("--prompt-file", default=None, help="使用已有提示词文件直接生图")

    args = parser.parse_args()

    for img_path in args.room_images:
        if not os.path.exists(img_path):
            print(f"Error: Room image not found: {img_path}")
            sys.exit(1)

    room_images_b64 = [encode_image(p) for p in args.room_images]
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    if args.prompt_file:
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            prompt_data = json.load(f)
        print(f"Loaded prompt from {args.prompt_file}")
    else:
        print(f"Fetching materials for IP '{args.ip_name}' region '{args.room_region}'...")
        materials = list_materials(args.ip_name, args.room_region)
        if not materials:
            print(f"No materials found for IP '{args.ip_name}' region '{args.room_region}'")
            sys.exit(1)
        print(f"Found {len(materials)} materials")

        print("Generating prompt...")
        prompt_data = call_generate_prompt(
            args.ip_name,
            args.room_region,
            room_images_b64,
            args.material_types,
            args.style_note,
        )
        prompt_file = Path(args.output_dir) / "prompt.json"
        with open(prompt_file, "w", encoding="utf-8") as f:
            json.dump(prompt_data, f, ensure_ascii=False, indent=2)
        print(f"Prompt saved to {prompt_file}")

    print(f"Placements: {len(prompt_data.get('material_placements', []))} materials")
    for mp in prompt_data.get("material_placements", []):
        print(f"  - {mp['material_type']}: {mp['placement']}")

    if args.prompt_only:
        print("Done (prompt only).")
        return

    print("Generating images...")
    saved = call_generate_images(
        prompt_data["prompt"],
        prompt_data.get("negative_prompt"),
        room_images_b64,
        args.max_images,
        args.output_dir,
    )

    print(f"\nDone! {len(saved)} images saved to {args.output_dir}")
    for s in saved:
        print(f"  {s}")


if __name__ == "__main__":
    main()
