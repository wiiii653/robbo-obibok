# POST_REFACTOR_PLAN.md

## 1. Podsumowanie refaktoru

Refaktór projektu `robbo-obibok` wprowadził spójną architekturę opartą na wzorcach projektowych, usprawnił zarządzanie stanem aplikacji oraz poprawił czytelność i testowalność kluczowych modułów. Zmniejszono powiązania między komponentami, wdrożono jednolite mechanizmy logowania oraz usunięto redundancję w obsłudze strumieni i procesów zewnętrznych.

## 2. Słabe punkty projektu

- **`playback_process/stream_runtime.py`**: obsługa subprocessów oparta na `subprocess.run()` bez asynchronicznej kontroli timeoutów i detekcji nieoczekiwanych exit codes, co powoduje zawieszanie wątków przy awariach FFmpeg/yt-dlp.
- **Brak integracji API Discorda**: brak implementacji `discord.py` botów, brak handlerów dla slash commands i interakcji, co ogranicza rozszerzalność platformy i uniemożliwia natywną komunikację z użytkownikami.
- **Niskie pokrycie testami integracyjnymi**: brak testów e2e dla pipeline'u audio/video, brak mocków dla zewnętrznych zależności w `tests/integration/`, co utrudnia wykrycie regresji po zmianach w warstwie infrastrukturalnej.

## 3. Rekomendacje

- **P1**: Wprowadzenie `asyncio.create_subprocess_exec()` w `stream_runtime.py` z timeoutem 30s i fallbackiem do `subprocess.Popen` z monitorowaniem PID.
- **P1**: Dodanie modułu `discord_bot.py` z handlerami `/play`, `/stop`, `/queue` oraz integracją z `discord.py` v2.0+.
- **P2**: Rozbudowa `tests/integration/test_stream_pipeline.py` o 3 scenariusze e2e z mockami `yt-dlp` i `ffmpeg`.
- **P2**: Wdrożenie `pydantic` dla walidacji konfiguracji w `config/settings.py` i usunięcie `dict`-based parsingu.
- **P3**: Dodanie CI/CD z automatycznym uruchamianiem `pytest --cov` i raportowaniem coverage >80%.

## 4. Technical debt do spłacenia

- `playback_process/stream_runtime.py`: ręczne zarządzanie wątkami (`threading.Thread`) zamiast `asyncio`/`concurrent.futures`.
- `config/settings.py`: hardcodowane ścieżki i brak walidacji schematu.
- `utils/logger.py`: brak strukturalnego logowania (JSON) i mieszanie `print()` z `logging`.
- `main.py`: monolityczna struktura z >500 liniami, brak rozdzielenia na warstwy (CLI, service, infrastructure).
- Brak `pyproject.toml`/`requirements.in` z pinowanymi wersjami zależności.

## 5. Rada roku

Trzymaj się zasady „single responsibility" – każdy moduł ma robić jedną rzecz i robić ją dobrze; nie naprawiaj wszystkiego naraz, lecz iteruj w małych, mierzalnych krokach.

*Jak mówi lubuska mądrość: „Gdy wiatr z zachodu wieje, a woda w stawach stoi, to i robota idzie, i czas się nie gubi."*
