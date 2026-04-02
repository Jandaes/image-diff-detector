# Image Diff Detector

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.5+-green.svg)](https://opencv.org/)
[![中文](https://img.shields.io/badge/Language-中文-blue.svg)](README_CN.md)

**A Python tool to detect and visualize differences between two images with automatic alignment support.**

Compare images, find diff regions, and generate visual markers - perfect for UI screenshot comparison, spot-the-difference games, and image version control.

**English Documentation** | **[中文文档](README_CN.md)**

## Features

- 🔍 **Automatic Image Alignment** - ORB feature matching + homography transformation handles different sizes, slight shifts, and scaling
- 🎯 **Precise Diff Detection** - Pixel-level comparison with morphological processing for accurate region detection
- 🖼️ **Visual Marking** - Red bounding boxes on original image + binary diff mask output
- 🔧 **Noise Filtering** - Configurable threshold and minimum area to ignore irrelevant noise
- 💻 **CLI & Module** - Use as command-line tool or import as Python module

## Installation

```bash
git clone https://github.com/Jandaes/image-diff-detector.git
cd image-diff-detector
pip install -r requirements.txt
```

Dependencies: `opencv-python >= 4.5.0`, `numpy >= 1.20.0`

## Quick Start

```bash
python diff_detector.py image1.png image2.png
```

Outputs:
- `diff_mask.png` - Binary mask highlighting diff regions (white = difference)
- `diff_marked.png` - Original image with red boxes around diff areas

## Demo

### Input Images

| Image A | Image B |
|:------:|:------:|
| ![Image A](a.png) | ![Image B](b.png) |

Two images with different dimensions (504×852 vs 508×798) and content variations.

### Detection Result

```bash
python diff_detector.py a.png b.png
```

**Marked Output:**

![Diff Marked](diff_marked.png)

**Diff Mask:**

![Diff Mask](diff_mask.png)

## Usage

### Command Line

```bash
python diff_detector.py <image1> <image2> [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--threshold`, `-t` | 25 | Diff sensitivity (0-255), lower = more sensitive |
| `--min-area`, `-a` | 100 | Minimum region area in pixels, filters noise |
| `--kernel-size`, `-k` | 5 | Morphological kernel size |
| `--output`, `-o` | Same as input | Output directory |
| `--prefix`, `-p` | diff | Output filename prefix |
| `--match-threshold` | 0.75 | Feature match quality threshold |

### Tuning Tips

**Detect subtle differences:**
```bash
python diff_detector.py img1.png img2.png --threshold 15 --min-area 50
```

**Ignore small noise:**
```bash
python diff_detector.py img1.png img2.png --threshold 40 --min-area 500
```

**Images with significant shift:**
```bash
python diff_detector.py img1.png img2.png --match-threshold 0.6
```

### Python Module

```python
from diff_detector import ImageDiffDetector

detector = ImageDiffDetector(threshold=25, min_area=100)
result = detector.detect("image1.png", "image2.png")

for region in result["regions"]:
    print(f"Position: ({region['x']}, {region['y']})")
    print(f"Size: {region['width']}x{region['height']}")

# Output paths
print(result["mask_path"])
print(result["marked_path"])
```

## Algorithm

```
Image A ──┐
          ├──► Feature Detection (ORB) ──► Matching ──► Alignment (Homography)
Image B ──┘
                                                          │
                                                          ▼
                                              Grayscale + AbsDiff
                                                          │
                                                          ▼
                                              Threshold + Morphology
                                                          │
                                                          ▼
                                              Contour Detection + Area Filter
                                                          │
                                                          ▼
                                              Visual Marking (Bounding Boxes)
```

## Use Cases

- 📱 UI screenshot version comparison
- 🎮 Spot-the-difference game image analysis
- 📄 Document/poster change detection
- 🖌️ Design revision tracking

## Limitations

- Not suitable for large angle rotation (>15°)
- Not for completely different content or heavy occlusion
- Extreme lighting changes may affect detection
- No semantic description of differences (e.g., "button added")

## Project Structure

```
image-diff-detector/
├── diff_detector.py      # Main program
├── requirements.txt      # Dependencies
├── README.md             # Documentation
├── .gitignore            # Git ignore rules
├── a.png                 # Demo image A
├── b.png                 # Demo image B
├── diff_mask.png         # Output: diff mask
└── diff_marked.png       # Output: marked image
```

## License

MIT License