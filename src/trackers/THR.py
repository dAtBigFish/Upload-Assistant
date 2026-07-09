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
        meta_category = str(meta.get('category', ''))
        is_disc = str(meta.get('is_disc', ''))
        sd = int(meta.get('sd', 0) or 0)
        cat_id = '17'  # Default to Filmovi/HD

        if 'documentary' in genres or 'documentary' in keywords:
            cat_id = '12'
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

        return {'category_id': cat_id}

    async def get_name(self, meta: Meta) -> dict[str, str]:
        # Copied original naming logic from the old THR.py to ensure naming consistency
        from unidecode import unidecode
        import re
        
        thr_name = unidecode(str(meta.get('name', '')).replace('DD+', 'DDP'))
        torrent_name = re.sub(r"[^0-9a-zA-Z. '\-\[\]]+", " ", thr_name)
        
        return {'name': torrent_name}
