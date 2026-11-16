from PIL import Image, ImageDraw
S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
# 세로 그라데이션 배경 (둥근 사각형)
top = (24, 74, 104); bot = (12, 45, 64)
grad = Image.new("RGB", (1, S))
for y in range(S):
    t = y / (S - 1)
    grad.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
grad = grad.resize((S, S))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.225), fill=255)
img.paste(grad, (0, 0), mask)
d = ImageDraw.Draw(img)
# 안쪽 얇은 테두리
d.rounded_rectangle([8, 8, S - 9, S - 9], radius=int(S * 0.215), outline=(255, 255, 255, 34), width=6)
# 종이비행기(위를 향한 화살)
cx = S / 2
pts = [(cx, S * 0.215), (S * 0.795, S * 0.79), (cx, S * 0.645), (S * 0.205, S * 0.79)]
d.polygon(pts, fill=(255, 255, 255, 255))
# 접힌 부분 음영
d.polygon([(cx, S * 0.215), (cx, S * 0.645), (S * 0.205, S * 0.79)], fill=(255, 255, 255, 255))
d.polygon([(cx, S * 0.44), (S * 0.66, S * 0.755), (cx, S * 0.645)], fill=(214, 232, 243, 255))
for size, name in ((512, "icon-512.png"), (192, "icon-192.png"), (180, "icon-180.png")):
    img.resize((size, size), Image.LANCZOS).save(name)
print("icons done")
