"""Resolve local public proxy settings without printing credential contents."""
import os
from pathlib import Path
import sys
import tomllib


def configure():
    config = Path.home() / '.codex/config.toml'
    if not config.is_file():
        return
    try:
        profile = tomllib.loads(config.read_text())
        provider = profile.get('model_providers', {}).get(profile.get('model_provider'), {})
        if profile.get('model'):
            os.environ.setdefault('OPENAI_MODEL', profile['model'])
        if provider.get('base_url'):
            os.environ.setdefault('OPENAI_BASE_URL', provider['base_url'])
        key = Path.home() / '.codex/underclass-overalls.key'
        if (not os.environ.get('OPENAI_API_KEY') and not os.environ.get('OPENAI_API_KEY_FILE')
                and key.is_file() and 'underclass' in str(profile.get('model_provider', '')).lower()
                and os.environ.get('OPENAI_BASE_URL') == provider.get('base_url')):
            os.environ['OPENAI_API_KEY_FILE'] = str(key)
    except (OSError, ValueError):
        print('Local Codex configuration could not be loaded; use explicit OpenAI settings.', file=sys.stderr)
