#!/usr/bin/env python3

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import requests
import yaml

CDN_BASE_URL = os.environ.get("CDN_BASE_URL", "https://cdn.deephacking.tech")
CDN_UPLOAD_TOKEN = os.environ.get("CDN_UPLOAD_TOKEN", "")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
IMAGES_FOLDER_NAME = "images"
MAX_IMAGE_ID_SEARCH = 500

IMAGE_SIGNATURES = {
    b'\x89PNG\r\n\x1a\n': 'png',
    b'\xff\xd8\xff': 'jpeg',
    b'GIF87a': 'gif',
    b'GIF89a': 'gif',
    b'RIFF': 'webp',
    b'\x00\x00\x00': 'avif',
    b'BM': 'bmp',
}

EXTENSION_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".gif": "image/gif",
}

FRONTMATTER_PATTERN = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+["\'][^"\']*["\'])?\)')


class ImageRef(NamedTuple):
    original_ref: str
    full_match: str
    resolved_path: Path | None
    alt_text: str
    is_cover: bool = False


@dataclass
class ProcessingResult:
    md_path: Path
    slug: str
    images_processed: int = 0
    images_uploaded: int = 0
    errors: list[str] = field(default_factory=list)
    success: bool = True


def validate_image_file(file_path: Path) -> tuple[bool, str]:
    if not file_path.exists():
        return False, "File does not exist"
    
    if not file_path.is_file():
        return False, "Not a file"
    
    try:
        with open(file_path, 'rb') as f:
            header = f.read(32)
    except IOError as e:
        return False, f"Cannot read file: {e}"
    
    if len(header) < 4:
        return False, "File too small to be an image"
    
    for signature, img_type in IMAGE_SIGNATURES.items():
        if header.startswith(signature):
            if signature == b'RIFF' and b'WEBP' not in header[:12]:
                continue
            if signature == b'\x00\x00\x00' and b'ftyp' not in header[:12]:
                continue
            return True, img_type
    
    return False, "Unknown or invalid image format"


def parse_frontmatter(content: str) -> tuple[dict, str, int]:
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        return {}, content, 0
    
    try:
        frontmatter = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        frontmatter = {}
    
    body = content[match.end():]
    return frontmatter, body, match.end()


def extract_slug_from_frontmatter(frontmatter: dict, md_path: Path) -> str:
    slug = frontmatter.get('id', '').strip()
    if slug:
        return slug
    return md_path.stem


def extract_image_references(
    content: str, 
    md_path: Path, 
    images_dir: Path | None
) -> list[ImageRef]:
    refs = []
    
    for match in IMAGE_PATTERN.finditer(content):
        alt_text = match.group(1)
        img_ref = match.group(2)
        full_match = match.group(0)
        
        if img_ref.startswith(('http://', 'https://', '//')):
            continue
        
        resolved = (md_path.parent / img_ref).resolve()
        
        if images_dir and resolved.exists():
            try:
                resolved.relative_to(images_dir)
                refs.append(ImageRef(
                    original_ref=img_ref,
                    full_match=full_match,
                    resolved_path=resolved,
                    alt_text=alt_text,
                    is_cover=False,
                ))
            except ValueError:
                pass
    
    return refs


def check_cdn_image_exists(slug: str, image_id: int, extension: str = "avif") -> bool:
    url = f"{CDN_BASE_URL}/i/posts/{slug}/{slug}-{image_id}.{extension}"
    try:
        response = requests.head(url, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


def get_next_available_id(slug: str) -> int:
    for i in range(1, MAX_IMAGE_ID_SEARCH):
        if not check_cdn_image_exists(slug, i, "avif"):
            return i
    raise RuntimeError(f"No available image IDs found for slug: {slug}")


def get_existing_image_ids(slug: str) -> set[int]:
    existing = set()
    for i in range(0, MAX_IMAGE_ID_SEARCH):
        ext = "webp" if i == 0 else "avif"
        if check_cdn_image_exists(slug, i, ext):
            existing.add(i)
        elif i > 0 and not check_cdn_image_exists(slug, i, "avif"):
            if i > max(existing, default=0) + 10:
                break
    return existing


def optimize_cover(src: Path, dst: Path) -> None:
    subprocess.run([
        "convert", str(src),
        "-resize", "1200x630^",
        "-gravity", "center",
        "-extent", "1200x630",
        "-quality", "90",
        "-strip",
        str(dst)
    ], check=True, capture_output=True)


def optimize_content(src: Path, dst: Path) -> None:
    subprocess.run([
        "convert", str(src),
        "-quality", "60",
        "-strip",
        str(dst)
    ], check=True, capture_output=True)


def upload_to_cdn(file_path: Path, cdn_key: str) -> bool:
    if DRY_RUN:
        print(f"  [DRY-RUN] Would upload: {cdn_key}")
        return True
    
    url = f"{CDN_BASE_URL}/i/{cdn_key}"
    
    ext = file_path.suffix.lower()
    mime_type = EXTENSION_TO_MIME.get(ext, "application/octet-stream")
    
    headers = {
        "Authorization": f"Bearer {CDN_UPLOAD_TOKEN}",
        "Content-Type": mime_type,
    }
    
    try:
        with open(file_path, 'rb') as f:
            response = requests.put(url, data=f, headers=headers, timeout=60)
        
        if response.status_code == 201:
            print(f"  [✓] Uploaded: {cdn_key}")
            return True
        else:
            print(f"  [✗] Upload failed ({response.status_code}): {cdn_key}")
            return False
    except requests.RequestException as e:
        print(f"  [✗] Upload error: {e}")
        return False


@dataclass
class ArticleGroup:
    article_id: str
    md_files: list[Path] = field(default_factory=list)
    images_dir: Path | None = None
    source_md: Path | None = None


@dataclass 
class ImageToProcess:
    filename: str
    resolved_path: Path
    assigned_id: int
    is_cover: bool
    cdn_url: str = ""


def group_articles_by_id(md_files: list[Path]) -> dict[str, ArticleGroup]:
    groups: dict[str, ArticleGroup] = {}
    
    for md_path in md_files:
        if not md_path.exists():
            continue
            
        content = md_path.read_text(encoding='utf-8')
        frontmatter, _, _ = parse_frontmatter(content)
        article_id = extract_slug_from_frontmatter(frontmatter, md_path)
        
        if article_id not in groups:
            groups[article_id] = ArticleGroup(article_id=article_id)
        
        groups[article_id].md_files.append(md_path)
        
        images_dir = md_path.parent / IMAGES_FOLDER_NAME
        if images_dir.exists() and images_dir.is_dir():
            groups[article_id].images_dir = images_dir
            groups[article_id].source_md = md_path
    
    return groups


def collect_all_image_references(
    group: ArticleGroup
) -> tuple[dict[Path, list[tuple[Path, str]]], str | None]:
    image_to_mds: dict[Path, list[tuple[Path, str]]] = {}
    cover_ref: str | None = None
    cover_path: Path | None = None
    
    if not group.images_dir:
        return {}, None
    
    for md_path in group.md_files:
        content = md_path.read_text(encoding='utf-8')
        frontmatter, body, _ = parse_frontmatter(content)
        
        fm_cover = frontmatter.get('image', '')
        if fm_cover and not fm_cover.startswith(('http://', 'https://')):
            potential_cover = (group.images_dir / Path(fm_cover).name).resolve()
            if not potential_cover.exists():
                potential_cover = (md_path.parent / fm_cover).resolve()
            
            if potential_cover.exists():
                is_valid, _ = validate_image_file(potential_cover)
                if is_valid:
                    cover_path = potential_cover
                    cover_ref = fm_cover
                    if potential_cover not in image_to_mds:
                        image_to_mds[potential_cover] = []
                    image_to_mds[potential_cover].append((md_path, fm_cover))
        
        for match in IMAGE_PATTERN.finditer(body):
            img_ref = match.group(2)
            
            if img_ref.startswith(('http://', 'https://', '//')):
                continue
            
            img_filename = Path(img_ref).name
            resolved = (group.images_dir / img_filename).resolve()
            
            if not resolved.exists():
                resolved = (md_path.parent / img_ref).resolve()
            
            if resolved.exists():
                is_valid, _ = validate_image_file(resolved)
                if is_valid:
                    if resolved not in image_to_mds:
                        image_to_mds[resolved] = []
                    image_to_mds[resolved].append((md_path, img_ref))
    
    return image_to_mds, cover_ref


def process_article_group(group: ArticleGroup) -> ProcessingResult:
    result = ProcessingResult(
        md_path=group.source_md or group.md_files[0],
        slug=group.article_id
    )
    
    mode_label = "[DRY-RUN MODE]" if DRY_RUN else "[PRODUCTION MODE]"
    print(f"\n{'='*60}")
    print(f"{mode_label} Processing article group: {group.article_id}")
    print(f"Files in group: {[str(f) for f in group.md_files]}")
    print(f"Images folder: {group.images_dir or 'none'}")
    print(f"{'='*60}")
    
    if not group.images_dir:
        print("No images folder found in any language variant")
        return result
    
    image_to_mds, cover_ref = collect_all_image_references(group)
    
    if not image_to_mds:
        print("No valid images found")
        return result
    
    cover_path: Path | None = None
    if cover_ref:
        for img_path in image_to_mds.keys():
            if any(ref == cover_ref for _, ref in image_to_mds[img_path]):
                cover_path = img_path
                break
    
    print(f"\nUnique images found: {len(image_to_mds)}")
    for img_path, mds in image_to_mds.items():
        is_cover = img_path == cover_path
        print(f"  {'[COVER]' if is_cover else '[CONTENT]'} {img_path.name} → used by {len(mds)} file(s)")
    
    print("\nChecking existing images in CDN...")
    existing_ids = get_existing_image_ids(group.article_id)
    print(f"Existing IDs in CDN: {sorted(existing_ids) if existing_ids else 'none'}")
    
    images_to_process: list[ImageToProcess] = []
    next_content_id = max(existing_ids, default=0) + 1 if existing_ids else 1
    
    if cover_path:
        images_to_process.append(ImageToProcess(
            filename=cover_path.name,
            resolved_path=cover_path,
            assigned_id=0,
            is_cover=True,
        ))
    
    for img_path in image_to_mds.keys():
        if img_path == cover_path:
            continue
        
        images_to_process.append(ImageToProcess(
            filename=img_path.name,
            resolved_path=img_path,
            assigned_id=next_content_id,
            is_cover=False,
        ))
        next_content_id += 1
    
    print(f"\nID assignments:")
    for img in images_to_process:
        print(f"  {img.filename} → ID {img.assigned_id} ({'cover' if img.is_cover else 'content'})")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        for img in images_to_process:
            if img.is_cover:
                ext = "webp"
                optimized = tmp_path / f"{group.article_id}-{img.assigned_id}.webp"
                print(f"\nOptimizing cover: {img.filename} → {optimized.name}")
                try:
                    optimize_cover(img.resolved_path, optimized)
                except subprocess.CalledProcessError as e:
                    result.errors.append(f"Failed to optimize cover {img.filename}: {e}")
                    continue
            else:
                ext = "avif"
                optimized = tmp_path / f"{group.article_id}-{img.assigned_id}.avif"
                print(f"\nOptimizing: {img.filename} → {optimized.name}")
                try:
                    optimize_content(img.resolved_path, optimized)
                except subprocess.CalledProcessError as e:
                    result.errors.append(f"Failed to optimize {img.filename}: {e}")
                    continue
            
            cdn_key = f"posts/{group.article_id}/{group.article_id}-{img.assigned_id}.{ext}"
            cdn_url = f"{CDN_BASE_URL}/i/{cdn_key}"
            
            if upload_to_cdn(optimized, cdn_key):
                img.cdn_url = cdn_url
                result.images_uploaded += 1
            else:
                img.cdn_url = cdn_url
            
            result.images_processed += 1
    
    print(f"\nUpdating {len(group.md_files)} Markdown files...")
    
    if DRY_RUN:
        print("  [DRY-RUN] Skipping file updates")
        for md_path in group.md_files:
            print(f"  [·] Would update: {md_path}")
    else:
        for md_path in group.md_files:
            content = md_path.read_text(encoding='utf-8')
            new_content = content
            replacements_made = 0
            
            for img in images_to_process:
                if not img.cdn_url:
                    continue
                
                for source_md, original_ref in image_to_mds.get(img.resolved_path, []):
                    if source_md != md_path:
                        continue
                    
                    if img.is_cover:
                        new_content = new_content.replace(
                            f"image: {original_ref}",
                            f"image: {img.cdn_url}",
                            1
                        )
                        new_content = new_content.replace(
                            f'image: "{original_ref}"',
                            f'image: "{img.cdn_url}"',
                            1
                        )
                        new_content = new_content.replace(
                            f"image: '{original_ref}'",
                            f"image: '{img.cdn_url}'",
                            1
                        )
                        replacements_made += 1
                    else:
                        pattern = re.compile(
                            rf'!\[([^\]]*)\]\({re.escape(original_ref)}(?:\s+["\'][^"\']*["\'])?\)'
                        )
                        new_content, n = pattern.subn(rf'![\1]({img.cdn_url})', new_content)
                        replacements_made += n
            
            if new_content != content:
                md_path.write_text(new_content, encoding='utf-8')
                print(f"  [✓] Updated: {md_path} ({replacements_made} replacements)")
            else:
                print(f"  [·] No changes: {md_path}")
    
    if group.images_dir and group.images_dir.exists():
        if DRY_RUN:
            print(f"\n[DRY-RUN] Would remove images folder: {group.images_dir}")
        else:
            print(f"\nRemoving images folder: {group.images_dir}")
            shutil.rmtree(group.images_dir)
            print("[✓] Images folder removed")
    
    print(f"\n{'─'*60}")
    print(f"Summary for {group.article_id}:")
    print(f"  Files updated: {len(group.md_files)}")
    print(f"  Unique images: {len(images_to_process)}")
    print(f"  Images processed: {result.images_processed}")
    print(f"  Images uploaded: {result.images_uploaded}")
    if result.errors:
        print(f"  Errors: {len(result.errors)}")
        for err in result.errors:
            print(f"    - {err}")
    print(f"{'─'*60}")
    
    return result


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python process_images.py <file1.md> [file2.md ...]")
        return 1
    
    mode_label = "DRY-RUN (validation only)" if DRY_RUN else "PRODUCTION (will upload to CDN)"
    print(f"\n{'='*60}")
    print(f"MODE: {mode_label}")
    print(f"{'='*60}")
    
    if not DRY_RUN and not CDN_UPLOAD_TOKEN:
        print("Error: CDN_UPLOAD_TOKEN environment variable not set")
        return 1
    
    if shutil.which("convert") is None:
        print("Error: ImageMagick (convert) not found in PATH")
        return 1
    
    md_files = [Path(f) for f in sys.argv[1:] if f.endswith('.md')]
    
    if not md_files:
        print("No markdown files to process")
        return 0
    
    print(f"Files to process: {len(md_files)}")
    
    groups = group_articles_by_id(md_files)
    print(f"Article groups (by frontmatter.id): {len(groups)}")
    
    results: list[ProcessingResult] = []
    for article_id, group in groups.items():
        result = process_article_group(group)
        results.append(result)
    
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    
    total_processed = sum(r.images_processed for r in results)
    total_uploaded = sum(r.images_uploaded for r in results)
    total_errors = sum(len(r.errors) for r in results)
    total_files = sum(len(g.md_files) for g in groups.values())
    
    print(f"Article groups processed: {len(results)}")
    print(f"Total markdown files updated: {total_files}")
    print(f"Total images processed: {total_processed}")
    print(f"Total images uploaded: {total_uploaded}")
    print(f"Total errors: {total_errors}")
    
    if total_errors > 0:
        print("\nErrors encountered:")
        for r in results:
            for err in r.errors:
                print(f"  [{r.slug}] {err}")
        return 1
    
    print("\n[✓] All articles processed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
