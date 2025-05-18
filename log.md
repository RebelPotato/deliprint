# 记录

## 20250514

打印机到手！安装了驱动。
用 zadig 把 usbprint（10？） 换成了 WinUSB，就能用 python 控制了，但得力原厂的配置就不管用了。

## 20250515

使用 contextlib 改进代码，现在能用我最爱的 with 语句了。

新版语句不能用，只能用 GS v 0 打印图片。

一张长图片可以分成好几张短图片打印，中间不移动纸图案就能连续。所以可以用 generator 挨个输出？

最大宽度就是 48 个字节（384 个像素），比这还宽的图片会被裁剪。

## 20250516

发现最妙参数：atkinson, threshold=199, power=1.5。

## 20250517

把 threshold 改成 207 也可以，字部分没那么白。

```python
rows = itertools.chain(
    whiten(open_image_rows(".assets/fuchun0.jpg"), threshold=223, power=1.5),
    whiten(open_image_rows(".assets/fuchun1.jpg"), threshold=207, power=1.5),
    whiten(open_image_rows(".assets/fuchun2.jpg"), threshold=207, power=1.5),
    whiten(open_image_rows(".assets/fuchun3.jpg"), threshold=207, power=1.5),
)
```
