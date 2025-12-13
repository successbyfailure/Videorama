"""
Videorama v2.0.0 - Path Template Engine
Generate file paths from templates with variable substitution
"""

import re
from typing import Dict, Any
from pathlib import Path


class PathTemplateEngine:
    """
    Engine for processing path templates with variables

    Templates example: "{genre}/{artist}/{album}/{track_number:02d} - {title}.{ext}"
    Variables: {title}, {artist}, {genre}, {year}, {track_number}, {ext}, etc.
    """

    # Pattern to match template variables: {var} or {var:format}
    VARIABLE_PATTERN = re.compile(r"\{(\w+)(?::([^}]+))?\}")

    @classmethod
    def render(cls, template: str, variables: Dict[str, Any]) -> str:
        """
        Render a path template with given variables

        Args:
            template: Template string (e.g., "{genre}/{artist}/{title}.{ext}")
            variables: Dictionary of variable values

        Returns:
            Rendered path string

        Example:
            >>> render("{genre}/{artist}/{title}.{ext}", {
            ...     "genre": "Rock",
            ...     "artist": "Queen",
            ...     "title": "Bohemian Rhapsody",
            ...     "ext": "mp3"
            ... })
            'Rock/Queen/Bohemian Rhapsody.mp3'
        """
        if not template:
            return ""

        def replace_var(match):
            var_name = match.group(1)
            var_format = match.group(2)

            # Get variable value
            value = variables.get(var_name, "")

            # Skip if value is None or empty
            if value is None or value == "":
                return ""

            # Apply formatting if specified
            if var_format:
                try:
                    # Handle integer formatting (e.g., :02d)
                    if "d" in var_format:
                        value = int(value)
                        return f"{value:{var_format}}"
                    # Handle string formatting
                    else:
                        return f"{value:{var_format}}"
                except (ValueError, TypeError):
                    return str(value)

            return str(value)

        # Replace all variables
        rendered = cls.VARIABLE_PATTERN.sub(replace_var, template)

        # Clean up path (remove empty parts, normalize)
        parts = [p.strip() for p in rendered.split("/") if p.strip()]
        rendered = "/".join(parts)

        # Sanitize filename (remove invalid characters)
        rendered = cls.sanitize_path(rendered)

        return rendered

    @staticmethod
    def sanitize_path(path: str) -> str:
        """
        Sanitize path by removing invalid characters

        Args:
            path: Path string

        Returns:
            Sanitized path
        """
        # Characters not allowed in filenames
        invalid_chars = '<>:"|?*'

        for char in invalid_chars:
            path = path.replace(char, "")

        # Replace multiple spaces with single space
        path = re.sub(r"\s+", " ", path)

        # Remove leading/trailing spaces from each path component
        parts = [p.strip() for p in path.split("/")]
        path = "/".join(parts)

        return path

    @classmethod
    def get_available_variables(cls) -> Dict[str, str]:
        """
        Get list of available template variables and their descriptions

        Returns:
            Dictionary of variable names and descriptions
        """
        return {
            # Common
            "title": "Title of the item",
            "ext": "File extension",
            "year": "Year",
            "month": "Month (1-12)",
            "day": "Day (1-31)",
            "date": "Full date (YYYY-MM-DD)",
            "uuid": "UUID of the entry",
            # Music
            "artist": "Artist/band name",
            "album": "Album name",
            "track_number": "Track number",
            "genre": "Genre",
            "composer": "Composer",
            # Video/Movies
            "director": "Director name",
            "resolution": "Resolution (1080p, 4k, etc.)",
            "language": "Language",
            # Series
            "show_title": "Series title",
            "season": "Season number",
            "episode": "Episode number",
            "episode_title": "Episode title",
            # General
            "uploader": "Original uploader",
            "platform": "Platform (youtube, instagram, etc.)",
            "category": "Category",
        }

    @classmethod
    def validate_template(cls, template: str) -> tuple[bool, str]:
        """
        Validate a template string

        Args:
            template: Template string

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not template:
            return True, ""

        try:
            # Check for unmatched braces
            if template.count("{") != template.count("}"):
                return False, "Unmatched braces in template"

            # Try to extract all variables
            variables = cls.VARIABLE_PATTERN.findall(template)

            # Check if variables are valid
            available_vars = set(cls.get_available_variables().keys())

            for var_name, _ in variables:
                if var_name not in available_vars:
                    return (
                        False,
                        f"Unknown variable: {var_name}. Available: {', '.join(sorted(available_vars))}",
                    )

            # Try a test render
            test_vars = {var: "test" for var, _ in variables}
            cls.render(template, test_vars)

            return True, ""

        except Exception as e:
            return False, f"Template validation error: {str(e)}"
