# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from typing import Any, Optional

from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class THR(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='THR')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'THR'
        self.base_url = 'https://www.torrenthr.org'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [""]
        pass

    async def get_category_id(
        self,
        meta: Meta,
        category: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        _ = (category, reverse, mapping_only)
        genres = str(meta.get('genres', '')).lower()
        keywords = str(meta.get('keywords', '')).lower()
        meta_category = str(meta.get('category', '')).upper()
        is_disc = str(meta.get('is_disc', ''))
        sd = int(meta.get('sd', 0) or 0)
        
        cat_id = None

        if 'documentary' in genres or 'documentary' in keywords:
            cat_id = '12'
        elif 'animation' in genres or 'animation' in keywords:
            cat_id = '18'
        elif meta_category == "MOVIE":
            if is_disc == "BMDV" or is_disc == "BDMV":
                cat_id = '40'
            elif is_disc in {"DVD", "HDDVD"}:
                cat_id = '14'
            else:
                cat_id = '4' if sd == 1 else '17'
        elif meta_category == "TV":
            cat_id = '7' if sd == 1 else '34'
        elif bool(meta.get('anime')):
            cat_id = '31'

        if cat_id is None:
            from rich.prompt import Prompt
            from rich.console import Console
            console = Console()
            
            categories = {
                "Filmovi/HD": "17",
                "Filmovi/SD": "4",
                "Serije/HD": "34",
                "Serije/SD": "7",
                "Filmovi/BD": "40",
                "Dokumentarni Filmovi": "12",
                "Crtani Filmovi": "18"
            }
            
            console.print("[yellow]THR Category could not be auto-detected. Please select a category:[/yellow]")
            choice = Prompt.ask("Category", choices=list(categories.keys()), default="Filmovi/HD")
            cat_id = categories[choice]

        return {'category_id': cat_id}

    async def get_name(self, meta: Meta) -> dict[str, str]:
        # Copied original naming logic from the old THR.py to ensure naming consistency
        from unidecode import unidecode
        import re
        
        thr_name = unidecode(str(meta.get('name', '')).replace('DD+', 'DDP'))
        torrent_name = re.sub(r"[^0-9a-zA-Z. '\-\[\]]+", " ", thr_name)
        
        return {'name': torrent_name}

    async def get_description(self, meta: Meta) -> dict[str, str]:
        import os
        import glob
        import httpx
        import aiofiles
        from src.console import console

        # We need to grab up to 4 images from the local tmp dir
        tmp_dir = os.path.join(str(meta['base_dir']), 'tmp', str(meta['uuid']))
        image_patterns: list[str] = ["*.png", ".[!.]*.png"]
        image_glob: list[str] = []
        for pattern in image_patterns:
            image_glob.extend(glob.glob(os.path.join(tmp_dir, pattern)))

        unwanted_patterns = ["FILE*", "PLAYLIST*", "POSTER*"]
        unwanted_files: set[str] = set()
        for pattern in unwanted_patterns:
            unwanted_files.update(glob.glob(os.path.join(tmp_dir, pattern)))
            hidden_pattern = f".{pattern}"
            unwanted_files.update(glob.glob(os.path.join(tmp_dir, hidden_pattern)))

        ordered_images: list[str] = []
        seen_images: set[str] = set()
        for image in image_glob:
            if image in unwanted_files or image in seen_images:
                continue
            seen_images.add(image)
            ordered_images.append(image)

        # Ensure we only take up to 4 images
        ordered_images = ordered_images[:4]
        
        image_list: list[str] = []
        image_api_key = str(self.config['TRACKERS']['THR'].get('img_api', '')).strip()
        
        if ordered_images and not image_api_key:
            console.print("[yellow]THR image API key is not configured, skipping custom screenshot upload for THR[/yellow]")
        
        for image in ordered_images:
            if not image_api_key:
                break

            url = "https://img2.torrenthr.org/api/1/upload"
            data: dict[str, Any] = {
                'key': image_api_key,
            }
            async with aiofiles.open(image, 'rb') as image_file:
                file_bytes = await image_file.read()
                
            try:
                async with httpx.AsyncClient(timeout=30.0) as image_client:
                    response = await image_client.post(
                        url,
                        data=data,
                        files={'source': (os.path.basename(image), file_bytes)},
                    )
                    response.raise_for_status()
                    response_data = response.json()
                    img_data = response_data.get('image', {})
                    img_url = str(img_data.get('url', '')).strip()
                    if img_url:
                        image_list.append(img_url)
            except Exception as e:
                console.print(f"[yellow]Failed to upload image {os.path.basename(image)} to THR image host: {e}[/yellow]")
        
        desc_parts = ["[center]\n"]
        thumbnail_size = self.config['DEFAULT'].get('thumbnail_size', '350')
        for img_index, img_url in enumerate(image_list):
            desc_parts.append(f"[url={img_url}][img={thumbnail_size}]{img_url}[/img][/url] ")
            
            # 2 images per row -> 2x2 grid
            if (img_index + 1) % 2 == 0:
                desc_parts.append("\n")
                
        desc_parts.append("[/center]")
        
        return {
            "description": "".join(desc_parts)
        }

    async def get_additional_data(self, meta: Meta) -> dict[str, str]:
        import aiofiles
        import bencodepy
        import hashlib
        from typing import cast, Callable, Any
        from src.console import console
        
        info_hash = ''
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"
        
        try:
            async with aiofiles.open(torrent_path, 'rb') as torrent_file:
                torrent_content = await torrent_file.read()
                
            bencode_module = cast(Any, bencodepy)
            decode = cast(Callable[[bytes], Any], bencode_module.decode)
            torrent_data = decode(torrent_content)
            
            if isinstance(torrent_data, dict):
                torrent_dict = cast(dict[bytes, Any], torrent_data)
                info_value = torrent_dict.get(b'info')
                
                if isinstance(info_value, dict):
                    encode = cast(Callable[[Any], bytes], bencode_module.encode)
                    info = encode(info_value)
                    info_hash = hashlib.sha1(info, usedforsecurity=False).hexdigest()
        except Exception as e:
            console.print(f"[red]Error computing info_hash in THR: {e}[/red]")
            
        if not info_hash:
            info_hash = str(meta.get('infohash', '')).strip()
            
        data: dict[str, str] = {}
        if info_hash:
            data['info_hash'] = info_hash
            
        return data
