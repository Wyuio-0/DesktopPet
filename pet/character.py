"""Character model: parse config.json and enumerate animation clips."""

import copy
import glob
import json
import os
import random


class Action:
    def __init__(self, name, cfg, base_dir):
        self.name = name
        self.cfg = dict(cfg)
        self.sprite = copy.deepcopy(cfg.get("sprite"))
        self.folder = os.path.join(base_dir, cfg.get("folder", name))
        self.interval = int(cfg.get("interval", 0))
        self.loop = bool(cfg.get("loop", False))
        self.random = bool(cfg.get("random", False))
        # How many extra times to replay the clip before advancing to `next`
        # (0 = play once). Lets a short "loop" clip hold for a few cycles
        # without looping forever, e.g. skill_begin -> skill_loop x2 -> idle.
        self.loop_count = int(cfg.get("loop_count", 0))
        self.next = cfg.get("next")
        self.clips = self._load_clips(cfg, base_dir)

    def _load_clips(self, cfg, base_dir):
        clips = cfg.get("clips", cfg.get("clip"))
        if clips:
            if isinstance(clips, str):
                clips = [clips]
            out = []
            for clip in clips:
                path = clip if os.path.isabs(clip) else os.path.join(base_dir, clip)
                if os.path.isfile(path):
                    out.append(path)
            return sorted(out)
        return sorted(glob.glob(os.path.join(self.folder, "*.webm")))

    def pick_clip(self):
        if not self.clips:
            return None
        return random.choice(self.clips) if self.random else self.clips[0]


class Character:
    def __init__(self, char_dir, appearance=None):
        self.dir = char_dir
        with open(os.path.join(char_dir, "config.json"), encoding="utf-8") as f:
            base_cfg = json.load(f)
        variants = base_cfg.get("appearances", {})
        if not isinstance(variants, dict):
            variants = {}
        variants = {key: value for key, value in variants.items()
                    if key != "default" and isinstance(value, dict)}
        base_label = base_cfg.get("default_appearance_name", "默认形象")
        self.available_appearances = (("default", base_label),) + tuple(
            (key, value.get("display_name", key)) for key, value in variants.items())
        self.appearance_key = (appearance if isinstance(appearance, str)
                               and appearance in variants else "default")
        self.appearance_name = dict(self.available_appearances)[self.appearance_key]
        self.cfg = copy.deepcopy(base_cfg)
        if self.appearance_key != "default":
            variant = variants[self.appearance_key]
            # Appearance changes only presentation. Identity, AI preferences,
            # voice paths and hotkeys continue to use the same character.
            for field in ("scale", "interactions", "rest"):
                if field in variant:
                    self.cfg[field] = copy.deepcopy(variant[field])
            if "actions" in variant:
                self.cfg["actions"] = {
                    **self.cfg.get("actions", {}),
                    **copy.deepcopy(variant["actions"]),
                }
        self.key = os.path.basename(char_dir)
        self.name = self.cfg.get("name", os.path.basename(char_dir))
        self.display_name = self.cfg.get("display_name", self.name)
        self.scale = float(self.cfg.get("scale", 1.0))
        self.interactions = self.cfg.get("interactions", {})
        self.actions = {
            name: Action(name, acfg, char_dir)
            for name, acfg in self.cfg.get("actions", {}).items()
        }

    def action(self, name):
        return self.actions.get(name)

    def interaction(self, event):
        """Map an interaction event (e.g. 'on_click') to an action name."""
        return self.interactions.get(event)
