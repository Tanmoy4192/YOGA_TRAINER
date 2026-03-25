"""
Optional Sarvam-powered voice coach for SKY Yoga.

Why this file exists:
1. The pose controllers already decide what the coach should say.
2. We only need a thin speech layer that turns those signals into audio.
3. That layer must be calm and sparse, so it avoids repetitive alerts.

Design goals:
- Keep network and audio playback work off the frame loop.
- Speak only high-value moments: phase changes, countdowns, corrections,
  hold reminders, rep milestones, and goal completion.
- Deduplicate messages aggressively so the coach does not nag every frame.
- Stay optional: if Sarvam is not installed or no API key is present,
  the rest of the application should still run unchanged.
"""
from __future__ import annotations

import base64
import hashlib
import math
import os
import re
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

try:
    # winsound is the lightest zero-dependency way to play WAV files on Windows.
    import winsound
except ImportError:  # pragma: no cover - non-Windows fallback
    winsound = None

try:
    # The official SDK keeps us aligned with Sarvam's latest auth and payload shape.
    from sarvamai import SarvamAI
except Exception:  # pragma: no cover - dependency may be absent in local dev
    SarvamAI = None


# Regex helpers let us collapse noisy frame-by-frame text into stable speech events.
_RE_HOLD_MORE = re.compile(r"hold for (\d+)s more", re.IGNORECASE)
_RE_KEEP_STEADY = re.compile(r"keep steady for ([0-9.]+)s", re.IGNORECASE)
_RE_NUMBER = re.compile(r"\d+(?:\.\d+)?")


@dataclass(frozen=True)
class VoiceFrame:
    """
    Snapshot of the current coaching state.

    A frozen dataclass makes each update explicit and easy to compare against
    the previous frame without accidental mutation.
    """

    exercise_key: str | None
    phase_id: str | None
    phase_name: str
    coach_state: str
    watch_msg: str
    message: str
    correct: bool
    rep_done: int
    rep_target: int
    hold_remaining: float
    paused: bool
    video_pos: float
    phase_active: float | None = None
    phase_end: float | None = None


@dataclass(frozen=True)
class _SpeechTask:
    """
    A queued speech item.

    We keep the payload tiny because the worker only needs the text and its
    dedupe key; every other decision is made before the task is queued.
    """

    text: str
    dedupe_key: str


def _clean_text(text: str | None) -> str:
    """Normalize whitespace so cache keys and dedupe keys stay stable."""
    return " ".join((text or "").split())


def _message_family(text: str) -> str:
    """
    Collapse number-only variants into one family.

    Example:
      "Correct - hold for 20s more"
      "Correct - hold for 19s more"
    should map to the same family so we do not speak both.
    """
    compact = _clean_text(text).lower()
    compact = compact.replace("—", "-")
    return _RE_NUMBER.sub("#", compact)


class SarvamVoiceCoach:
    """
    Sparse voice policy backed by Sarvam TTS.

    The public API is intentionally tiny:
    - warm_phase_prompts(phases)
    - update(frame)
    - shutdown()
    """

    def __init__(self):
        # Environment-based config keeps the integration easy to deploy.
        self._api_key = os.environ.get("SARVAM_API_SUBSCRIPTION_KEY", "").strip()
        self._language = os.environ.get("SARVAM_TTS_LANG", "en-IN").strip() or "en-IN"
        self._speaker = os.environ.get("SARVAM_TTS_SPEAKER", "shubh").strip() or "shubh"
        self._model = os.environ.get("SARVAM_TTS_MODEL", "bulbul:v3").strip() or "bulbul:v3"
        self._codec = "wav"  # WAV keeps playback simple with winsound.
        self._sample_rate = int(os.environ.get("SARVAM_TTS_SAMPLE_RATE", "16000"))
        self._pace = float(os.environ.get("SARVAM_TTS_PACE", "0.96"))
        self._temperature = float(os.environ.get("SARVAM_TTS_TEMPERATURE", "0.2"))
        self._debug = os.environ.get("SARVAM_VOICE_DEBUG", "").strip() == "1"

        # A temp cache avoids re-paying and re-waiting for repeated static prompts.
        cache_root = os.environ.get("SARVAM_TTS_CACHE_DIR", "").strip()
        if cache_root:
            self._cache_dir = Path(cache_root)
        else:
            self._cache_dir = Path(tempfile.gettempdir()) / "yoga_trainer_sarvam_voice"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # The queue lives behind a Condition so we can safely clear stale prompts.
        self._cv = threading.Condition()
        self._pending: deque[_SpeechTask] = deque()
        self._stop = False

        # These maps are the heart of the anti-repetition policy.
        self._last_notice_at: dict[str, float] = {}
        self._prefetched_keys: set[str] = set()
        self._phase_hold_markers: set[str] = set()
        self._countdown_markers: set[str] = set()

        # We compare against the prior frame to speak on transitions, not every frame.
        self._last_frame: VoiceFrame | None = None

        # Disable cleanly if any required runtime piece is missing.
        self.enabled = bool(self._api_key and SarvamAI and winsound)
        self._disabled_reason = self._detect_disabled_reason()

        if not self.enabled:
            print(f"[voice] Sarvam voice disabled: {self._disabled_reason}")
            self._client = None
            self._worker = None
            return

        # The official SDK is the least brittle integration point.
        self._client = SarvamAI(api_subscription_key=self._api_key)

        # A single worker keeps speech ordered and prevents overlapping playback.
        self._worker = threading.Thread(target=self._worker_loop, name="sarvam-voice", daemon=True)
        self._worker.start()
        print(f"[voice] Sarvam voice enabled ({self._model}, {self._speaker}, {self._language})")

        # Common prompts are prefetched once because they happen in every session.
        self._warm_texts_async(["Get ready.", "3", "2", "1", "Start now."])

    def _detect_disabled_reason(self) -> str:
        """Return a human-readable reason for the no-op mode."""
        if not self._api_key:
            return "missing SARVAM_API_SUBSCRIPTION_KEY"
        if SarvamAI is None:
            return "missing 'sarvamai' package"
        if winsound is None:
            return "audio playback currently supports Windows only"
        return "unknown reason"

    def warm_phase_prompts(self, phases: list[dict] | None):
        """
        Prefetch static phase instructions in the background.

        This follows the earlier integration advice: phase prompts are the most
        predictable sentences, so caching them gives the coach a much snappier feel.
        """
        if not self.enabled or not phases:
            return

        texts: list[str] = []
        for phase in phases:
            watch_msg = _clean_text(phase.get("watch_msg", ""))
            if watch_msg:
                texts.append(watch_msg)

        self._warm_texts_async(texts)

    def _warm_texts_async(self, texts: list[str]):
        """Warm cache in a separate thread so main coaching never waits on it."""
        if not self.enabled or not texts:
            return

        unique_texts = []
        for text in texts:
            key = self._cache_key(text)
            if key in self._prefetched_keys:
                continue
            self._prefetched_keys.add(key)
            unique_texts.append(text)

        if not unique_texts:
            return

        threading.Thread(
            target=self._warm_texts_worker,
            args=(tuple(unique_texts),),
            name="sarvam-voice-prefetch",
            daemon=True,
        ).start()

    def _warm_texts_worker(self, texts: tuple[str, ...]):
        """Sequential background prefetch keeps API traffic simple and predictable."""
        for text in texts:
            try:
                self._audio_path_for_text(text)
            except Exception as exc:  # pragma: no cover - best effort cache warm
                self._log(f"prefetch failed for '{text}': {exc}")

    def update(self, frame: VoiceFrame):
        """
        Consume the latest coach state and decide what should be spoken.

        This method is intentionally lightweight so it can be called every frame.
        All slow work is deferred to the worker thread.
        """
        if not self.enabled:
            return

        # Clean the raw strings once so all downstream logic sees stable text.
        frame = VoiceFrame(
            exercise_key=frame.exercise_key,
            phase_id=frame.phase_id,
            phase_name=_clean_text(frame.phase_name),
            coach_state=frame.coach_state,
            watch_msg=_clean_text(frame.watch_msg),
            message=_clean_text(frame.message),
            correct=frame.correct,
            rep_done=frame.rep_done,
            rep_target=frame.rep_target,
            hold_remaining=frame.hold_remaining,
            paused=frame.paused,
            video_pos=frame.video_pos,
            phase_active=frame.phase_active,
            phase_end=frame.phase_end,
        )

        previous = self._last_frame

        # Manual pause should stop new prompts from piling up behind the scenes.
        if frame.paused:
            self._last_frame = frame
            return

        self._maybe_speak_phase_prompt(previous, frame)
        self._maybe_speak_prepare_countdown(previous, frame)
        self._maybe_speak_active_start(previous, frame)
        self._maybe_speak_rep_progress(previous, frame)
        self._maybe_speak_hold_guidance(previous, frame)
        self._maybe_speak_message(previous, frame)

        self._last_frame = frame

    def _maybe_speak_phase_prompt(self, previous: VoiceFrame | None, frame: VoiceFrame):
        """Speak the phase instruction once when the user enters a new phase."""
        if not frame.phase_id or not frame.watch_msg:
            return

        if previous and previous.phase_id == frame.phase_id:
            return

        # Reset per-phase markers so each phase can speak its own countdown/hold milestones.
        self._reset_phase_markers(frame.phase_id)

        # Clearing the queue here prevents a stale correction from the prior phase being spoken late.
        self._enqueue(frame.watch_msg, f"phase:{frame.phase_id}", min_interval=3600.0, replace_queue=True)

    def _maybe_speak_prepare_countdown(self, previous: VoiceFrame | None, frame: VoiceFrame):
        """Count down only in the final prepare window, and only once per number."""
        if frame.coach_state != "PREPARE" or frame.phase_active is None:
            return

        seconds_left = max(0, int(math.ceil(frame.phase_active - frame.video_pos)))
        if seconds_left not in (1, 2, 3):
            return

        # If the phase just changed, the watch prompt has already spoken.
        # Skipping the first "Get ready" avoids a back-to-back double alert.
        if seconds_left == 3 and (previous is None or previous.phase_id != frame.phase_id):
            return

        marker = f"countdown:{frame.phase_id}:{seconds_left}"
        if marker in self._countdown_markers:
            return

        self._countdown_markers.add(marker)

        # "Get ready" is friendlier than speaking "3" without context the first time.
        text = "Get ready." if seconds_left == 3 else str(seconds_left)
        self._enqueue(text, marker, min_interval=3600.0)

    def _maybe_speak_active_start(self, previous: VoiceFrame | None, frame: VoiceFrame):
        """A short 'Start now' cue gives the user a clear handoff from watching to doing."""
        if frame.coach_state != "ACTIVE":
            return
        if previous and previous.coach_state == "ACTIVE" and previous.phase_id == frame.phase_id:
            return
        if not frame.phase_id:
            return

        self._enqueue("Start now.", f"active-start:{frame.phase_id}", min_interval=3600.0)

    def _maybe_speak_rep_progress(self, previous: VoiceFrame | None, frame: VoiceFrame):
        """Speak milestones only when the rep counter actually advances."""
        if frame.rep_target <= 0 or frame.rep_done <= 0 or not frame.phase_id:
            return

        prev_done = 0
        if previous and previous.phase_id == frame.phase_id:
            prev_done = previous.rep_done

        if frame.rep_done <= prev_done:
            return

        if frame.rep_done >= frame.rep_target:
            text = frame.message or f"Good job. Target reached. {frame.rep_done} of {frame.rep_target}."
            self._enqueue(text, f"rep-goal:{frame.phase_id}", min_interval=3600.0, replace_queue=True)
            return

        # Mid-set progress is helpful, but we keep it compact.
        text = f"{frame.rep_done} of {frame.rep_target}"
        self._enqueue(text, f"rep:{frame.phase_id}:{frame.rep_done}", min_interval=3600.0)

    def _maybe_speak_hold_guidance(self, previous: VoiceFrame | None, frame: VoiceFrame):
        """
        Handle two different hold styles:
        1. BaseController HOLD after a phase misses its target.
        2. In-phase hold guidance such as acupressure.
        """
        if not frame.phase_id:
            return

        if frame.coach_state == "HOLD":
            if not previous or previous.coach_state != "HOLD" or previous.phase_id != frame.phase_id:
                text = frame.message or "Pause here and complete the remaining repetitions."
                self._enqueue(text, f"hold-enter:{frame.phase_id}", min_interval=3600.0, replace_queue=True)

            # A single midpoint reminder keeps the coach present without nagging.
            if frame.hold_remaining <= 5.0:
                self._enqueue(
                    frame.message or "Still paused. Finish the remaining repetitions.",
                    f"hold-mid:{frame.phase_id}",
                    min_interval=3600.0,
                )
            return

        # "Correct - keep steady for 1.2s." is useful only the first time we lock onto the target.
        if _RE_KEEP_STEADY.search(frame.message):
            self._enqueue("Good. Hold steady.", f"steady:{frame.phase_id}", min_interval=3600.0)
            return

        # "Correct - hold for 29s more." changes every second, so we only speak milestone buckets.
        match = _RE_HOLD_MORE.search(frame.message)
        if not match:
            return

        remaining = int(match.group(1))
        for threshold in (20, 10, 5):
            marker = f"phase-hold:{frame.phase_id}:{threshold}"
            if remaining <= threshold and marker not in self._phase_hold_markers:
                self._phase_hold_markers.add(marker)
                text = f"Good. Hold for {threshold} more seconds."
                self._enqueue(text, marker, min_interval=3600.0)
                break

    def _maybe_speak_message(self, previous: VoiceFrame | None, frame: VoiceFrame):
        """
        Speak corrective or supportive messages that are not already handled elsewhere.

        This is deliberately conservative. Generic success chatter is skipped so the
        voice coach feels focused rather than constantly talkative.
        """
        message = frame.message
        if not message or not frame.phase_id:
            return

        # WATCH/PREPARE prompts already come from watch_msg and countdown logic.
        if frame.coach_state in ("WATCH", "PREPARE", "ZOOM"):
            return

        # We handle hold-specific messages with dedicated throttle rules.
        if frame.coach_state == "HOLD":
            return
        if _RE_KEEP_STEADY.search(message) or _RE_HOLD_MORE.search(message):
            return

        lower = message.lower()

        # Generic praise is skipped unless it represents a real milestone.
        if lower.startswith("good form"):
            return

        if lower.startswith("good job") or lower.startswith("great work"):
            self._enqueue(message, f"success:{frame.phase_id}", min_interval=3600.0, replace_queue=True)
            return

        family = _message_family(message)
        prev_family = _message_family(previous.message) if previous and previous.phase_id == frame.phase_id else ""

        # A new correction should be spoken quickly; the same one should cool down.
        min_interval = 2.0 if family != prev_family else 6.0
        self._enqueue(message, f"msg:{frame.phase_id}:{family}", min_interval=min_interval, replace_queue=(family != prev_family))

    def _reset_phase_markers(self, phase_id: str):
        """Clear any per-phase markers when a new phase begins."""
        self._phase_hold_markers = {m for m in self._phase_hold_markers if not m.startswith(f"phase-hold:{phase_id}:")}
        self._countdown_markers = {m for m in self._countdown_markers if not m.startswith(f"countdown:{phase_id}:")}

    def _enqueue(self, text: str, dedupe_key: str, *, min_interval: float, replace_queue: bool = False):
        """
        Add a prompt to the queue if it is not too repetitive.

        `min_interval` is the main anti-repeat lever. It applies before queueing,
        so repeated frames do not flood the worker.
        """
        text = _clean_text(text)
        if not text:
            return

        now = time.monotonic()
        if now - self._last_notice_at.get(dedupe_key, -1e9) < min_interval:
            return
        self._last_notice_at[dedupe_key] = now

        with self._cv:
            if replace_queue:
                self._pending.clear()

            # Drop the oldest stale prompt when the queue is full.
            while len(self._pending) >= 6:
                self._pending.popleft()

            self._pending.append(_SpeechTask(text=text, dedupe_key=dedupe_key))
            self._cv.notify()

    def _worker_loop(self):
        """Fetch audio and play it sequentially so speech never overlaps."""
        while True:
            with self._cv:
                while not self._pending and not self._stop:
                    self._cv.wait(timeout=0.5)

                if self._stop:
                    return

                task = self._pending.popleft()

            try:
                audio_path = self._audio_path_for_text(task.text)
                if audio_path is None:
                    continue
                self._play_audio(audio_path)
            except Exception as exc:  # pragma: no cover - defensive runtime guard
                self._log(f"worker error for '{task.text}': {exc}")

    def _cache_key(self, text: str) -> str:
        """Hash text plus synthesis settings so cache files stay deterministic."""
        payload = "|".join(
            [
                self._model,
                self._language,
                self._speaker,
                self._codec,
                str(self._sample_rate),
                f"{self._pace:.3f}",
                f"{self._temperature:.3f}",
                _clean_text(text),
            ]
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def _audio_path_for_text(self, text: str) -> Path | None:
        """
        Return a cached WAV path for text, synthesizing it once when needed.

        Keeping this logic in one place makes both prefetch and live playback
        share the same cache behavior.
        """
        key = self._cache_key(text)
        path = self._cache_dir / f"{key}.wav"
        if path.exists():
            return path

        response = self._client.text_to_speech.convert(
            text=text,
            target_language_code=self._language,
            model=self._model,
            speaker=self._speaker,
            pace=self._pace,
            temperature=self._temperature,
            output_audio_codec=self._codec,
            speech_sample_rate=self._sample_rate,
        )

        # The SDK may expose response fields as attributes or as a dict-like object.
        audios = getattr(response, "audios", None)
        if audios is None and isinstance(response, dict):
            audios = response.get("audios")
        if not audios:
            self._log(f"no audio returned for '{text}'")
            return None

        audio_bytes = base64.b64decode(audios[0])
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_bytes(audio_bytes)
        tmp_path.replace(path)
        return path

    def _play_audio(self, audio_path: Path):
        """Play the generated WAV synchronously inside the worker thread."""
        winsound.PlaySound(str(audio_path), winsound.SND_FILENAME)

    def shutdown(self):
        """Stop the worker cleanly when the application exits."""
        if not self.enabled or not self._worker:
            return

        with self._cv:
            self._stop = True
            self._pending.clear()
            self._cv.notify_all()

        self._worker.join(timeout=2.0)

    def _log(self, message: str):
        """Tiny debug helper so normal runs stay quiet."""
        if self._debug:
            print(f"[voice] {message}")
