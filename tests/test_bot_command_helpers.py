import sys
import types
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archive_catalog import ArchiveCatalog
from archive_runtime import ArchiveRuntime, ArchiveRuntimeConfig
from test_support import (
    FakeContext,
    FakeVoiceChannel,
    FakeVoiceClient,
    MagicMock,
    RegistrationBot,
    patch,
    unittest,
)

import bot_events
import entrypoint_checks
import library_commands
import playback_handlers
import playback_commands
import session_runtime


def build_archive_runtime_fixture():
    logger = types.SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )
    config = ArchiveRuntimeConfig()
    archives = ArchiveCatalog(paths=config, logger=logger)
    archive_runtime = ArchiveRuntime(
        archives=archives,
        logger=logger,
        snes_spc_dir="",
        temp_dir="/tmp",
        build_temp_path=lambda url: f"/tmp/{Path(url).name}",
        get_shared_session=lambda: None,
        config=config,
    )
    return types.SimpleNamespace(
        archives=archives,
        archive_runtime=archive_runtime,
    )


class DummyDeps:
    def __init__(self, **overrides):
        self._overrides = overrides

    def __getattr__(self, name):
        if name in self._overrides:
            return self._overrides[name]
        if name in {"mod_only"}:
            return lambda: (lambda func: func)
        if name.isupper():
            return ""
        return lambda *args, **kwargs: None


class CommandRegistrationTests(unittest.TestCase):
    def test_playback_commands_register_expected_names_and_aliases(self):
        fake_bot = RegistrationBot()
        playback_commands.register_playback_commands(fake_bot, DummyDeps())

        expected = {
            "play": {"radio", "start", "pl"},
            "stop": {"st"},
            "skip": {"next", "nt"},
            "np": set(),
            "volume": set(),
            "queue": {"q"},
            "sleep": set(),
            "loop": {"repeat"},
            "history": set(),
            "jump": set(),
            "clear": set(),
            "ocko": set(),
            "help": set(),
            "export": set(),
            "refresh": set(),
            "reindex": set(),
            "stats": set(),
            "search": set(),
            "hvsc": {"c64", "sid"},
            "asma": set(),
            "mod": {"modarchive", "tracker", "modules"},
            "ay": {"zx", "zxspectrum", "spectrum"},
            "ym": {"atarist", "ym2149"},
            "tiny": {"tm", "demoscene"},
            "snes_cmd": {"snes", "spc", "supernintendo", "nintendo"},
            "status": {"mode", "collection", "all"},
            "flip": {"switch", "toggle", "fl"},
        }

        self.assertEqual(set(fake_bot.commands), set(expected))
        for name, aliases in expected.items():
            self.assertEqual(set(fake_bot.commands[name]["aliases"]), aliases)

    def test_library_commands_register_expected_names_and_events(self):
        fake_bot = RegistrationBot()
        library_commands.register_library_commands(fake_bot, DummyDeps())

        expected_commands = {
            "favorites": {"favs", "playlist"},
            "favplay": {"fp"},
            "favsave": {"pls"},
            "favload": {"fpl"},
            "playlists": {"plist", "list-playlists", "playlist-dir"},
            "blacklist_track": {"blk"},
            "blacklist_list": {"blks", "blklist"},
            "blacklist_remove": {"blkrm"},
        }

        self.assertEqual(set(fake_bot.commands), set(expected_commands))
        for name, aliases in expected_commands.items():
            self.assertEqual(set(fake_bot.commands[name]["aliases"]), aliases)

        self.assertEqual(set(fake_bot.events), {"on_raw_reaction_add", "on_raw_reaction_remove"})

    def test_playback_handlers_builder_exposes_all_collection_routes(self):
        handlers = playback_handlers.build_playback_handlers(
            DummyDeps(
                ASMA_DIR="",
                AY_DIR="",
                HVSC_DIR="",
                TINY_DIR="",
                YM_DIR="",
            )
        )

        self.assertEqual(
            set(handlers),
            {"asma", "ay", "hvsc", "modarchive", "spc", "tiny", "ym"},
        )

    def test_collection_info_is_typed(self):
        info = build_archive_runtime_fixture().archives.get_collection_info("asma")

        self.assertEqual(info.station, "ASMA Radio")
        self.assertEqual(info.footer, "ASMA Radio")


class SessionRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_metadata_background_indexes_local_sap_headers(self):
        fixture = build_archive_runtime_fixture()
        temp_dir = ROOT / "tmp" / "session_runtime"
        temp_dir.mkdir(parents=True, exist_ok=True)
        sap_path = temp_dir / "track.sap"
        sap_path.write_text('SAP\nAUTHOR "Tester"\nNAME "Example"\n', encoding="utf-8")
        saved = []
        metadata_index = {}

        deps = session_runtime.MetadataSessionDependencies(
            asma_dir=str(temp_dir),
            has_metadata_entry=lambda path: path in metadata_index,
            load_asma_local_cache=lambda: ["track.sap"],
            log=types.SimpleNamespace(info=lambda *a, **k: None),
            metadata_index_size=lambda: len(metadata_index),
            parse_sap_header=fixture.archive_runtime.parse_sap_header,
            save_metadata_cache=lambda data: saved.append(dict(data)),
            snapshot_metadata_index=lambda: dict(metadata_index),
            store_metadata_entry=lambda path, meta: metadata_index.__setitem__(path, meta),
        )
        fake_bot = types.SimpleNamespace(wait_until_ready=self._true_async)

        with patch.object(session_runtime.asyncio, "sleep", self._fast_sleep):
            await session_runtime.fetch_metadata_background(fake_bot, deps)

        self.assertEqual(metadata_index["track.sap"]["AUTHOR"], "Tester")
        self.assertTrue(saved)

    async def _true_async(self, *_args, **_kwargs):
        return True

    async def _fast_sleep(self, *_args, **_kwargs):
        return None


class EventRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_register_core_events_registers_ready_and_voice_handlers(self):
        fake_bot = RegistrationBot()
        calls = []
        deps = bot_events.CoreEventDependencies(
            AUTO_START_CHANNEL="radio",
            PLAYBACK_LOOP=True,
            PLAYBACK_SHUFFLE=True,
            apply_queue_state=lambda *_args, **_kwargs: False,
            ensure_tracks=self._true_async,
            get_collection_info=lambda _mode: types.SimpleNamespace(station="ASMA Radio"),
            get_state=lambda _guild_id: types.SimpleNamespace(tracks=[]),
            load_queue=lambda _guild_id: None,
            log=types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None),
            log_preloaded_cache=lambda label, tracks: calls.append(("cache", label, tracks)),
            load_asma_local_cache=lambda: ["a"],
            load_hvsc_local_cache=lambda: ["b"],
            monitor_playback=self._true_async,
            play_current_track=self._true_async,
            prepare_playback_queue=lambda *args, **kwargs: {},
            run_startup_steps=self._true_async,
            save_queue=lambda _state: None,
            schedule_background_tasks=lambda tasks: calls.append(("tasks", len(tasks))),
        )

        bot_events.register_core_events(fake_bot, deps, health_watchdog=self._true_async, fetch_metadata_background=self._true_async)

        self.assertEqual(set(fake_bot.events), {"on_ready", "on_voice_state_update"})

    async def test_on_ready_runs_startup_before_cache_logging_and_background_tasks(self):
        fake_bot = RegistrationBot()
        calls = []

        async def run_startup_steps():
            calls.append("startup")

        deps = bot_events.CoreEventDependencies(
            AUTO_START_CHANNEL="radio",
            PLAYBACK_LOOP=True,
            PLAYBACK_SHUFFLE=True,
            apply_queue_state=lambda *_args, **_kwargs: False,
            ensure_tracks=self._true_async,
            get_collection_info=lambda _mode: types.SimpleNamespace(station="ASMA Radio"),
            get_state=lambda _guild_id: types.SimpleNamespace(tracks=[]),
            load_queue=lambda _guild_id: None,
            log=types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None),
            log_preloaded_cache=lambda label, tracks: calls.append((label, list(tracks or []))),
            load_asma_local_cache=lambda: ["asma"],
            load_hvsc_local_cache=lambda: ["hvsc"],
            monitor_playback=self._true_async,
            play_current_track=self._true_async,
            prepare_playback_queue=lambda *args, **kwargs: {},
            run_startup_steps=run_startup_steps,
            save_queue=lambda _state: None,
            schedule_background_tasks=lambda tasks: calls.append(("tasks", len(tasks))),
        )

        bot_events.register_core_events(
            fake_bot,
            deps,
            health_watchdog=self._true_async,
            fetch_metadata_background=self._true_async,
        )

        await fake_bot.events["on_ready"]()

        self.assertEqual(
            calls,
            [
                "startup",
                ("ASMA", ["asma"]),
                ("HVSC", ["hvsc"]),
                ("tasks", 2),
            ],
        )

    async def _true_async(self, *_args, **_kwargs):
        return True


class SingleGuildCheckTests(unittest.TestCase):
    def test_rejects_wrong_guild(self):
        guild_id = 12345
        single_guild_check = entrypoint_checks.build_single_guild_check(
            guild_id_getter=lambda: guild_id
        )
        ctx = MagicMock()
        ctx.guild.id = 99999
        self.assertFalse(single_guild_check(ctx))

    def test_allows_correct_guild(self):
        guild_id = 12345
        single_guild_check = entrypoint_checks.build_single_guild_check(
            guild_id_getter=lambda: guild_id
        )
        ctx = MagicMock()
        ctx.guild.id = 12345
        self.assertTrue(single_guild_check(ctx))

    def test_allows_when_unset(self):
        single_guild_check = entrypoint_checks.build_single_guild_check(
            guild_id_getter=lambda: None
        )
        ctx = MagicMock()
        ctx.guild.id = 99999
        self.assertTrue(single_guild_check(ctx))
