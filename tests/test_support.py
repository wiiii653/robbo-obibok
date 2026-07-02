import sys
import types
import unittest  # noqa: F401 — re-exported for other test modules
from pathlib import Path
from unittest.mock import MagicMock, patch  # noqa: F401 — re-exported for other test modules

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def install_discord_stubs():
    if "discord" in sys.modules:
        return

    discord = types.ModuleType("discord")

    class FakeAudioSource:
        pass

    class FakeIntents:
        message_content = False

        @classmethod
        def default(cls):
            return cls()

    class FakeColor:
        @staticmethod
        def purple():
            return "purple"

        @staticmethod
        def green():
            return "green"

        @staticmethod
        def blue():
            return "blue"

        @staticmethod
        def dark_blue():
            return "dark_blue"

        @staticmethod
        def from_str(_value):
            return "from_str"

    class FakeEmbed:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def add_field(self, *args, **kwargs):
            return None

        def set_footer(self, *args, **kwargs):
            return None

    discord.AudioSource = FakeAudioSource
    discord.Intents = FakeIntents
    discord.Color = FakeColor
    discord.Embed = FakeEmbed
    discord.Member = type("Member", (), {})
    discord.VoiceState = type("VoiceState", (), {})
    discord.VoiceClient = type("VoiceClient", (), {})
    discord.RawReactionActionEvent = type("RawReactionActionEvent", (), {})

    ext = types.ModuleType("discord.ext")
    commands = types.ModuleType("discord.ext.commands")

    class FakeBot:
        def __init__(self, *args, **kwargs):
            self.owner = object()
            self.loop = types.SimpleNamespace(create_task=lambda coro: coro)
            self.voice_clients = []

        def remove_command(self, _name):
            return None

        def check(self, func):
            return func

        def event(self, func):
            return func

        def command(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

        def run(self, *_args, **_kwargs):
            return None

        async def close(self):
            return None

        async def wait_until_ready(self):
            return None

        def is_closed(self):
            return False

    class FakeBucketType:
        guild = "guild"

    class FakeMissingPermissions(Exception):
        pass

    def passthrough_decorator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    commands.Bot = FakeBot
    commands.Context = object
    commands.BucketType = FakeBucketType
    commands.MissingPermissions = FakeMissingPermissions
    commands.check = passthrough_decorator
    commands.cooldown = passthrough_decorator

    sys.modules["discord"] = discord
    sys.modules["discord.ext"] = ext
    sys.modules["discord.ext.commands"] = commands


install_discord_stubs()

class RegistrationBot:
    def __init__(self):
        self.commands = {}
        self.events = {}
        self.scheduled = []
        self.user = "test-bot"
        self.loop = types.SimpleNamespace(create_task=self._create_task)

    def command(self, *args, **kwargs):
        aliases = tuple(kwargs.get("aliases", []))
        explicit_name = kwargs.get("name")

        def decorator(func):
            name = explicit_name or func.__name__
            self.commands[name] = {"func": func, "aliases": aliases}
            return func

        return decorator

    def event(self, func):
        self.events[func.__name__] = func
        return func

    def _create_task(self, coro):
        self.scheduled.append(coro)
        coro.close()
        return types.SimpleNamespace(done=lambda: False, cancel=lambda: None)


class FakeVoiceClient:
    def __init__(self):
        self.disconnected = False
        self.channel = types.SimpleNamespace(members=[object(), object()])

    async def disconnect(self):
        self.disconnected = True

    def is_connected(self):
        return not self.disconnected


class FakeVoiceChannel:
    def __init__(self, voice_client):
        self.voice_client = voice_client

    async def connect(self):
        return self.voice_client


class FakeContext:
    def __init__(self, guild_id=1, author_id=7, voice_client=None):
        self.guild = types.SimpleNamespace(id=guild_id, name="Test Guild")
        self.voice_client = voice_client
        self.sent = []
        self.author = types.SimpleNamespace(
            id=author_id,
            voice=types.SimpleNamespace(channel=FakeVoiceChannel(FakeVoiceClient())),
        )

    async def send(self, content=None, embed=None):
        message = types.SimpleNamespace(id=len(self.sent) + 1, content=content, embed=embed)
        self.sent.append(message)
        return message
