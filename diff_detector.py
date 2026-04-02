#!/usr/bin/env python3
"""
图片内容差异检测工具

对比两张图片，自动找出内容差异并进行可视化标记。
支持不同尺寸图片的对齐，适用于UI截图对比、找茬等场景。
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import cv2
import numpy as np


class ImageDiffDetector:
    """图片差异检测器"""

    def __init__(
        self,
        threshold: int = 25,
        min_area: int = 100,
        kernel_size: int = 5,
        match_threshold: float = 0.75,
        min_matches: int = 10,
    ):
        """
        初始化检测器

        Args:
            threshold: 差异阈值 (0-255)，越小越敏感
            min_area: 最小差异区域面积（像素），过滤小噪点
            kernel_size: 形态学操作核大小
            match_threshold: 特征匹配质量阈值 (0-1)
            min_matches: 对齐所需最少匹配点数量
        """
        self.threshold = threshold
        self.min_area = min_area
        self.kernel_size = kernel_size
        self.match_threshold = match_threshold
        self.min_matches = min_matches

        # ORB 特征检测器
        self.orb = cv2.ORB_create(nfeatures=5000)

        # BF 匹配器
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    def load_image(self, path: str) -> np.ndarray:
        """加载图片"""
        img = cv2.imread(path)
        if img is None:
            raise ValueError(f"无法加载图片: {path}")
        return img

    def align_images(
        self, img1: np.ndarray, img2: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, bool]:
        """
        将 img2 对齐到 img1 的坐标系

        Args:
            img1: 参考图片
            img2: 待对齐图片

        Returns:
            (img1, aligned_img2, success): 对齐后的两张图片 + 是否成功
        """
        # 转灰度图用于特征检测
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        # 检测特征点和描述子
        kp1, desc1 = self.orb.detectAndCompute(gray1, None)
        kp2, desc2 = self.orb.detectAndCompute(gray2, None)

        # 检查是否有足够的特征点
        if desc1 is None or desc2 is None:
            print("警告: 无法检测到足够的特征点，使用简单尺寸调整")
            return self._resize_to_match(img1, img2)

        # 特征匹配
        matches = self.matcher.knnMatch(desc1, desc2, k=2)

        # 筛选优质匹配点 ( Lowe's ratio test )
        good_matches = []
        for match in matches:
            if len(match) == 2:
                m, n = match
                if m.distance < self.match_threshold * n.distance:
                    good_matches.append(m)

        if len(good_matches) < self.min_matches:
            print(f"警告: 优质匹配点不足 ({len(good_matches)} < {self.min_matches})，使用简单尺寸调整")
            return self._resize_to_match(img1, img2)

        # 获取匹配点坐标
        src_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        # 计算单应性矩阵 ( RANSAC 去除异常点 )
        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

        if H is None:
            print("警告: 无法计算单应性矩阵，使用简单尺寸调整")
            return self._resize_to_match(img1, img2)

        # 变换 img2 到 img1 的坐标系
        h1, w1 = img1.shape[:2]
        aligned_img2 = cv2.warpPerspective(img2, H, (w1, h1))

        return img1, aligned_img2, True

    def _resize_to_match(
        self, img1: np.ndarray, img2: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, bool]:
        """当对齐失败时，简单调整尺寸匹配"""
        h1, w1 = img1.shape[:2]
        resized_img2 = cv2.resize(img2, (w1, h1), interpolation=cv2.INTER_AREA)
        return img1, resized_img2, False

    def compute_diff(
        self, img1: np.ndarray, img2: np.ndarray
    ) -> np.ndarray:
        """
        计算两张图片的差异

        Args:
            img1, img2: 已对齐的两张图片

        Returns:
            diff_mask: 差异的二值 mask
        """
        # 转灰度图
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        # 计算绝对差分
        diff = cv2.absdiff(gray1, gray2)

        # 阈值处理得到二值 mask
        _, mask = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)

        return mask

    def post_process(self, mask: np.ndarray) -> np.ndarray:
        """
        形态学处理：去噪、合并相邻区域

        Args:
            mask: 原始差异 mask

        Returns:
            processed_mask: 处理后的 mask
        """
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (self.kernel_size, self.kernel_size)
        )

        # 开运算去除小噪点
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # 膨胀合并相邻区域
        mask = cv2.dilate(mask, kernel, iterations=2)

        return mask

    def find_regions(self, mask: np.ndarray) -> List[Dict]:
        """
        提取差异区域轮廓

        Args:
            mask: 处理后的差异 mask

        Returns:
            regions: 差异区域列表 [{x, y, w, h}, ...]
        """
        # 查找轮廓
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        regions = []
        for contour in contours:
            # 计算矩形边界
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h

            # 过滤面积过小的区域
            if area >= self.min_area:
                regions.append({
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "area": area
                })

        # 按面积排序（大的在前）
        regions.sort(key=lambda r: r["area"], reverse=True)

        return regions

    def mark_differences(
        self,
        img: np.ndarray,
        regions: List[Dict],
        color: Tuple[int, int, int] = (0, 0, 255),
        thickness: int = 2
    ) -> np.ndarray:
        """
        在图片上标记差异区域

        Args:
            img: 原始图片
            regions: 差异区域列表
            color: 标记颜色 (BGR)
            thickness: 矩形框厚度

        Returns:
            marked_img: 标记后的图片
        """
        marked_img = img.copy()

        for region in regions:
            x, y, w, h = region["x"], region["y"], region["width"], region["height"]
            cv2.rectangle(marked_img, (x, y), (x + w, y + h), color, thickness)

        return marked_img

    def detect(
        self,
        image_path1: str,
        image_path2: str,
        output_dir: Optional[str] = None,
        output_prefix: str = "diff"
    ) -> Dict:
        """
        主入口：检测两张图片的差异

        Args:
            image_path1: 第一张图片路径
            image_path2: 第二张图片路径
            output_dir: 输出目录，默认与第一张图片同目录
            output_prefix: 输出文件名前缀

        Returns:
            {
                "regions": 差异区域列表,
                "mask_path": mask 文件路径,
                "marked_path": 标记图文件路径,
                "aligned": 是否成功对齐
            }
        """
        # 加载图片
        img1 = self.load_image(image_path1)
        img2 = self.load_image(image_path2)

        print(f"图片1尺寸: {img1.shape[:2]}")
        print(f"图片2尺寸: {img2.shape[:2]}")

        # 对齐图片
        img1_aligned, img2_aligned, aligned_success = self.align_images(img1, img2)
        print(f"图片对齐: {'成功' if aligned_success else '使用简单尺寸调整'}")

        # 计算差异
        mask = self.compute_diff(img1_aligned, img2_aligned)

        # 形态学处理
        mask = self.post_process(mask)

        # 提取差异区域
        regions = self.find_regions(mask)
        print(f"检测到 {len(regions)} 个差异区域")

        # 确定输出目录
        if output_dir is None:
            output_dir = str(Path(image_path1).parent)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 保存差异 mask
        mask_path = output_dir / f"{output_prefix}_mask.png"
        cv2.imwrite(str(mask_path), mask)
        print(f"差异 mask 已保存: {mask_path}")

        # 保存标记后的图片
        marked_img = self.mark_differences(img1_aligned, regions)
        marked_path = output_dir / f"{output_prefix}_marked.png"
        cv2.imwrite(str(marked_path), marked_img)
        print(f"标记图片已保存: {marked_path}")

        return {
            "regions": regions,
            "mask_path": str(mask_path),
            "marked_path": str(marked_path),
            "aligned": aligned_success,
            "total_diff_area": sum(r["area"] for r in regions)
        }


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="图片内容差异检测工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python diff_detector.py image1.png image2.png
  python diff_detector.py img1.png img2.png --threshold 30 --min-area 200
  python diff_detector.py img1.png img2.png --output ./results --prefix compare
        """
    )

    parser.add_argument("image1", help="第一张图片路径")
    parser.add_argument("image2", help="第二张图片路径")

    parser.add_argument(
        "--threshold", "-t",
        type=int,
        default=25,
        help="差异阈值 (0-255)，越小越敏感 (默认: 25)"
    )

    parser.add_argument(
        "--min-area", "-a",
        type=int,
        default=100,
        help="最小差异区域面积（像素），过滤小噪点 (默认: 100)"
    )

    parser.add_argument(
        "--kernel-size", "-k",
        type=int,
        default=5,
        help="形态学操作核大小 (默认: 5)"
    )

    parser.add_argument(
        "--output", "-o",
        help="输出目录 (默认: 与第一张图片同目录)"
    )

    parser.add_argument(
        "--prefix", "-p",
        default="diff",
        help="输出文件名前缀 (默认: diff)"
    )

    parser.add_argument(
        "--match-threshold",
        type=float,
        default=0.75,
        help="特征匹配质量阈值 (默认: 0.75)"
    )

    args = parser.parse_args()

    # 创建检测器
    detector = ImageDiffDetector(
        threshold=args.threshold,
        min_area=args.min_area,
        kernel_size=args.kernel_size,
        match_threshold=args.match_threshold,
    )

    # 执行检测
    try:
        result = detector.detect(
            args.image1,
            args.image2,
            output_dir=args.output,
            output_prefix=args.prefix,
        )

        # 打印结果摘要
        print("\n=== 检测结果 ===")
        print(f"差异区域数量: {len(result['regions'])}")
        print(f"总差异面积: {result['total_diff_area']} 像素")

        if result['regions']:
            print("\n差异区域坐标:")
            for i, region in enumerate(result['regions'], 1):
                print(f"  {i}. ({region['x']}, {region['y']}) "
                      f"{region['width']}x{region['height']} "
                      f"面积={region['area']}")

        print(f"\n输出文件:")
        print(f"  - {result['mask_path']}")
        print(f"  - {result['marked_path']}")

    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()