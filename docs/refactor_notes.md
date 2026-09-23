# Refactor notes

## Baseline selected from the archive

- Autonomous driving: `Auto_Driver_client2.py` + `user4.py`
- Data collection: `Data_Coll4.py`
- MCU firmware: `sketch_oct31a/sketch_oct31a.ino`

These were selected because they contain the broadest/final feature set, and `Auto_Driver_client2.py` / `Data_Coll4.py` are also among the latest modified versions in the supplied archive.

## Removed as duplicate, scratch, generated, or unused

| Original item | Action | Reason |
|---|---|---|
| `Auto_Driver.py`, `Auto_Driver_client.py`, `Auto_Driver_client3.py`, `Auto_Driver_client_follow.py`, `Auto_Data_Coll*.py` | Removed from clean tree | Earlier/alternate branches with heavy duplication |
| `Data_Coll3.py` | Removed | Superseded by `Data_Coll4.py` |
| `user.py`, `user2.py`, `user3.py` | Removed | Alternate course behaviors; final refactor is based on `user4.py` |
| `__pycache__/` | Removed | Generated Python cache |
| `.vscode/settings.json` | Removed | Personal editor state |
| `Image.py` | Removed | Vendored Pillow module; not project code |
| `# Copyright ...txt` | Removed | Unused PaddlePaddle augmentation snippet |
| `0.py`, `cap.py`, `hsv.py`, `files_check.py`, `read_npy.py`, `rename.py`, `sort.py`, `re.py`, malformed scratch files | Removed/replaced | One-off local utilities, hard-coded Windows paths, incomplete code, or module-name conflicts |
| `number_judge.py` | Removed | Empty/unused stub |
| `resnet.py` | Removed | Standalone SGE-ResNet definition not referenced by the runtime |

## Bugs / risks fixed in the clean implementation

- `user4.py` referenced `used` without defining it; stop-line handling is now explicit one-shot state.
- `pre_vle` typo no longer silently prevents intended speed updates.
- `limited=True` was immediately overwritten by `slow == False -> pre_vel=1600`; speed-limit state now has deterministic priority.
- One global `number` counter was shared by every detection class; counters are now per class.
- The old behavior loop could invoke `send_cmd` repeatedly for one object/frame through many independent `if/else` blocks; the refactor produces one frame-level decision plus explicit timed maneuvers.
- Model/debug code that tried to `cv2.imdecode` a float tensor and wrote `zzzzz_test.jpg` every inference was removed.
- Hard-coded absolute training paths were replaced by repository-relative configuration.
- Data collection no longer needs `num_data.txt`; the next image ID is inferred from existing files and labels are stored in CSV.
- MCU stop logic checked `sp == 1500` *after subtracting 1500*; it now correctly checks the throttle delta against zero.

## Compatibility choices intentionally preserved

- The lane-model tensor path defaults to the original direct NHWC-to-NCHW reshape (`legacy_memory_layout=true`). It looks unusual, but changing it could invalidate a model trained/deployed with that behavior.
- The MCU packet decoder keeps the original base-255 reconstruction because the matching `libart_driver.so` is not present. Changing it to normal base-256 without seeing the sender could break the serial protocol.
- Cone-related labels 5-8 are exposed as detected events only. The supplied `user4.py` counted them but did not contain a complete maneuver, so the refactor does not invent one.
