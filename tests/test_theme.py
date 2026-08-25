"""Тесты нормализации темы — регрессия на ('dark', 'is not a valid theme.')."""

import json

import pytest

from core.utils import DEFAULT_THEME, ConfigManager, normalize_theme


class TestNormalizeTheme:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("dark", "darkly"),
            ("DARK", "darkly"),
            ("  Dark  ", "darkly"),
            ("light", "cosmo"),
            ("default", DEFAULT_THEME),
            ("", DEFAULT_THEME),
            (None, DEFAULT_THEME),
            ("darkly", "darkly"),
            ("Superhero", "superhero"),
        ],
    )
    def test_aliases_and_defaults(self, value, expected):
        assert normalize_theme(value) == expected

    def test_unknown_theme_is_kept(self):
        """Незнакомые имена не вырезаются: валидность проверяет слой GUI."""
        assert normalize_theme("Morph") == "morph"
        assert normalize_theme("united") == "united"


class TestConfigThemeMigration:
    def test_invalid_theme_is_migrated_on_load(self, isolated_home, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")

        config = ConfigManager(config_path=str(config_path))

        assert config.get("theme") == "darkly"
        saved = json.loads(config_path.read_text(encoding="utf-8"))
        assert saved["theme"] == "darkly"

    def test_valid_theme_is_not_touched(self, isolated_home, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"theme": "superhero"}), encoding="utf-8")
        config = ConfigManager(config_path=str(config_path))
        assert config.get("theme") == "superhero"

    def test_set_and_update_normalize_theme(self, isolated_home, tmp_path):
        config = ConfigManager(config_path=str(tmp_path / "config.json"))
        config.set("theme", "light")
        assert config.get("theme") == "cosmo"
        config.update({"theme": "dark"})
        assert config.get("theme") == "darkly"
