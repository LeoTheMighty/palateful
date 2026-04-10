# Minimal transforms shim providing what HunYuanVLImageProcessor needs.
# Avoids importing full torchvision which requires C extensions.

from enum import IntEnum

import torch
from PIL import Image
import numpy as np


class InterpolationMode(IntEnum):
    NEAREST = 0
    LANCZOS = 1
    BILINEAR = 2
    BICUBIC = 3
    BOX = 4
    HAMMING = 5


class Compose:
    def __init__(self, transforms):
        self.transforms = transforms

    def __call__(self, img):
        for t in self.transforms:
            img = t(img)
        return img


class Resize:
    def __init__(self, size, interpolation=InterpolationMode.BILINEAR, **kwargs):
        if isinstance(size, int):
            self.size = (size, size)
        else:
            self.size = tuple(size)

    def __call__(self, img):
        if isinstance(img, Image.Image):
            return img.resize((self.size[1], self.size[0]), Image.BILINEAR)
        return img


class ToTensor:
    def __call__(self, pic):
        if isinstance(pic, Image.Image):
            img = np.array(pic)
            if img.ndim == 2:
                img = img[:, :, np.newaxis]
            img = img.transpose((2, 0, 1))
            return torch.from_numpy(img.copy()).float().div(255.0)
        return pic


class Normalize:
    def __init__(self, mean, std):
        self.mean = torch.tensor(mean).float()
        self.std = torch.tensor(std).float()

    def __call__(self, tensor):
        if tensor.ndim == 3:
            self.mean = self.mean.view(-1, 1, 1)
            self.std = self.std.view(-1, 1, 1)
        return (tensor - self.mean) / self.std


class CenterCrop:
    def __init__(self, size):
        if isinstance(size, int):
            self.size = (size, size)
        else:
            self.size = tuple(size)

    def __call__(self, img):
        if isinstance(img, Image.Image):
            w, h = img.size
            th, tw = self.size
            x = (w - tw) // 2
            y = (h - th) // 2
            return img.crop((x, y, x + tw, y + th))
        return img


class ToPILImage:
    def __call__(self, tensor):
        if isinstance(tensor, torch.Tensor):
            img = tensor.mul(255).byte().numpy()
            if img.ndim == 3:
                img = img.transpose((1, 2, 0))
            return Image.fromarray(img)
        return tensor
