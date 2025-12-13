"""
Videorama v2.0.0 - External APIs
Integration with iTunes, TMDb, MusicBrainz for metadata enrichment
"""

import httpx
from typing import Optional, Dict, Any, List
from ..config import settings


class iTunesAPI:
    """iTunes Search API integration for music metadata"""

    BASE_URL = "https://itunes.apple.com/search"

    @staticmethod
    async def search(
        query: str, media_type: str = "music", limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search iTunes for music metadata

        Args:
            query: Search query (artist + song name)
            media_type: Media type (music, movie, podcast)
            limit: Number of results

        Returns:
            List of results
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    iTunesAPI.BASE_URL,
                    params={
                        "term": query,
                        "media": media_type,
                        "limit": limit,
                        "entity": "song",
                    },
                    timeout=10.0,
                )

                response.raise_for_status()
                data = response.json()

                return data.get("results", [])

            except Exception as e:
                print(f"iTunes API error: {e}")
                return []

    @staticmethod
    def extract_metadata(result: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract useful metadata from iTunes result

        Args:
            result: iTunes API result

        Returns:
            Cleaned metadata dict
        """
        return {
            "artist": result.get("artistName", ""),
            "album": result.get("collectionName", ""),
            "title": result.get("trackName", ""),
            "genre": result.get("primaryGenreName", ""),
            "year": result.get("releaseDate", "")[:4] if result.get("releaseDate") else "",
            "track_number": str(result.get("trackNumber", "")),
            "duration": str(result.get("trackTimeMillis", 0) // 1000),  # Convert to seconds
            "artwork_url": result.get("artworkUrl100", "").replace("100x100", "600x600"),
        }


class TMDbAPI:
    """The Movie Database API integration for movie/TV metadata"""

    BASE_URL = "https://api.themoviedb.org/3"

    @staticmethod
    async def search_movie(query: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search TMDb for movie

        Args:
            query: Movie title
            year: Optional release year

        Returns:
            List of results
        """
        if not settings.TMDB_API_KEY:
            return []

        async with httpx.AsyncClient() as client:
            try:
                params = {
                    "api_key": settings.TMDB_API_KEY,
                    "query": query,
                    "language": "es-ES",
                }

                if year:
                    params["year"] = year

                response = await client.get(
                    f"{TMDbAPI.BASE_URL}/search/movie",
                    params=params,
                    timeout=10.0,
                )

                response.raise_for_status()
                data = response.json()

                return data.get("results", [])

            except Exception as e:
                print(f"TMDb API error: {e}")
                return []

    @staticmethod
    async def get_movie_details(movie_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed movie information

        Args:
            movie_id: TMDb movie ID

        Returns:
            Movie details or None
        """
        if not settings.TMDB_API_KEY:
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{TMDbAPI.BASE_URL}/movie/{movie_id}",
                    params={
                        "api_key": settings.TMDB_API_KEY,
                        "append_to_response": "credits",
                        "language": "es-ES",
                    },
                    timeout=10.0,
                )

                response.raise_for_status()
                return response.json()

            except Exception as e:
                print(f"TMDb details error: {e}")
                return None

    @staticmethod
    def extract_metadata(result: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract useful metadata from TMDb result

        Args:
            result: TMDb API result

        Returns:
            Cleaned metadata dict
        """
        # Get director from credits if available
        director = ""
        if "credits" in result and "crew" in result["credits"]:
            directors = [
                person["name"]
                for person in result["credits"]["crew"]
                if person.get("job") == "Director"
            ]
            director = ", ".join(directors)

        # Get main cast
        cast = ""
        if "credits" in result and "cast" in result["credits"]:
            cast_list = [person["name"] for person in result["credits"]["cast"][:5]]
            cast = ", ".join(cast_list)

        return {
            "title": result.get("title", ""),
            "year": result.get("release_date", "")[:4] if result.get("release_date") else "",
            "genre": ", ".join([g["name"] for g in result.get("genres", [])]),
            "director": director,
            "cast": cast,
            "description": result.get("overview", ""),
            "rating": str(result.get("vote_average", "")),
            "language": result.get("original_language", ""),
            "poster_url": f"https://image.tmdb.org/t/p/w500{result['poster_path']}"
            if result.get("poster_path")
            else "",
        }


class MusicBrainzAPI:
    """MusicBrainz API integration for music metadata"""

    BASE_URL = "https://musicbrainz.org/ws/2"
    USER_AGENT = "Videorama/2.0.0 (https://github.com/successbyfailure/Videorama)"

    @staticmethod
    async def search_recording(artist: str, track: str) -> List[Dict[str, Any]]:
        """
        Search MusicBrainz for recording

        Args:
            artist: Artist name
            track: Track name

        Returns:
            List of results
        """
        async with httpx.AsyncClient() as client:
            try:
                query = f'artist:"{artist}" AND recording:"{track}"'

                response = await client.get(
                    f"{MusicBrainzAPI.BASE_URL}/recording",
                    params={
                        "query": query,
                        "fmt": "json",
                        "limit": 5,
                    },
                    headers={"User-Agent": MusicBrainzAPI.USER_AGENT},
                    timeout=10.0,
                )

                response.raise_for_status()
                data = response.json()

                return data.get("recordings", [])

            except Exception as e:
                print(f"MusicBrainz API error: {e}")
                return []

    @staticmethod
    def extract_metadata(result: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract useful metadata from MusicBrainz result

        Args:
            result: MusicBrainz API result

        Returns:
            Cleaned metadata dict
        """
        # Get first release info
        release = result.get("releases", [{}])[0] if result.get("releases") else {}

        return {
            "title": result.get("title", ""),
            "artist": result.get("artist-credit", [{}])[0].get("name", "") if result.get("artist-credit") else "",
            "album": release.get("title", ""),
            "year": release.get("date", "")[:4] if release.get("date") else "",
            "duration": str(result.get("length", 0) // 1000) if result.get("length") else "",  # ms to seconds
        }


# Convenience function to enrich from all sources
async def enrich_metadata(
    title: str,
    media_type: str = "music",
    artist: Optional[str] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Enrich metadata from all available external sources

    Args:
        title: Title to search for
        media_type: Type of media ('music' or 'movie')
        artist: Artist name (for music)
        year: Release year (for movies)

    Returns:
        Enriched metadata from all sources
    """
    enriched = {}

    if media_type == "music":
        # Try iTunes
        query = f"{artist} {title}" if artist else title
        itunes_results = await iTunesAPI.search(query, limit=1)

        if itunes_results:
            enriched["itunes"] = iTunesAPI.extract_metadata(itunes_results[0])

        # Try MusicBrainz
        if artist:
            mb_results = await MusicBrainzAPI.search_recording(artist, title)
            if mb_results:
                enriched["musicbrainz"] = MusicBrainzAPI.extract_metadata(mb_results[0])

    elif media_type == "movie":
        # Try TMDb
        tmdb_results = await TMDbAPI.search_movie(title, year)

        if tmdb_results:
            movie_id = tmdb_results[0]["id"]
            details = await TMDbAPI.get_movie_details(movie_id)

            if details:
                enriched["tmdb"] = TMDbAPI.extract_metadata(details)

    return enriched
