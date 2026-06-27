"""
技能：拼豆图纸生成（阶段2 升级版）
================================
按 data/a.jpg 的风格：每个格子是【正方形】+ 中间写【色号】+ 红色网格 + 材料清单。
  - 使用 Artkal-S 5mm 官方色卡（159 个真实色号 S01–S159），数据来源 pixel-beads.com
  - 自动判断合适的豆板尺寸（保持长宽比不拉伸）
  - 输入是卡通/插画/动漫时，本地算法零成本即可，无需 AI

输入：图片路径（+ 可选 size，不传则自动）
输出：图纸存到 data/outputs/bead_pattern_<输入图名>.png，返回材料清单文字
"""
import os                              # 路径操作、创建目录
import numpy as np                     # 数组运算（向量化配色，快）
from PIL import Image, ImageDraw, ImageFont  # 画图（Pillow 库）
from skimage import color as skcolor   # 颜色空间转换（RGB ↔ Lab）


def _hex2rgb(h):
    """把 "#FFD100" 这样的十六进制颜色转成 (R, G, B) 元组。"""
    h = h.lstrip("#")  # 去掉开头的 #
    # 每 2 位一组，按 16 进制转成整数：i=0→R, i=2→G, i=4→B
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ---------- Artkal-S 5mm 官方色卡（159 色）----------
# 每一项格式：(色号, 颜色名, HEX)。这是真实可买的拼豆颜色。
# 下面 S01~S159 共 159 行，格式统一，不逐行注释；重点是它们都是「真实色号」。
BEAD_PALETTE = [
    ("S01", "White", "#FFFFFF"), ("S02", "Burning Sand", "#FFA38B"),
    ("S03", "Tangerine", "#F6AD4C"), ("S04", "Orange", "#FF671F"),
    ("S05", "Tall Poppy", "#E10600"), ("S06", "Raspberry Pink", "#EC86D0"),
    ("S07", "Gray", "#9B9B9B"), ("S08", "Emerald", "#24DE5B"),
    ("S09", "Dark Green", "#00685E"), ("S10", "Baby Blue", "#41B6E6"),
    ("S11", "Dark Blue", "#003399"), ("S12", "Pastel Lavender", "#A05EB5"),
    ("S13", "Black", "#000000"), ("S14", "Sandstorm", "#FAE053"),
    ("S15", "Redwood", "#793E2C"), ("S16", "Brown", "#5C4738"),
    ("S17", "Light Brown", "#7B4D35"), ("S18", "Sand", "#CC9966"),
    ("S19", "Bubble Gum", "#FCBFA9"), ("S20", "Green", "#249E6B"),
    ("S21", "Pastel Green", "#87D839"), ("S22", "Purple", "#330072"),
    ("S23", "Royal Purple", "#64359B"), ("S24", "True Blue", "#147BD1"),
    ("S25", "Hot Pink", "#FF34B3"), ("S26", "Magenta", "#DB2152"),
    ("S27", "Yellow", "#FFD100"), ("S28", "Lily Pink", "#EAB8E4"),
    ("S29", "Pastel Yellow", "#F6EB61"), ("S30", "Shadow Green", "#99D6EA"),
    ("S31", "Sea Mist", "#9EE5B0"), ("S32", "Beeswax", "#FFE780"),
    ("S33", "Maverick", "#C5B4E3"), ("S34", "Red", "#BA0C2F"),
    ("S35", "Mona Lisa", "#F7CED7"), ("S36", "Old Pink", "#C9809E"),
    ("S37", "Blue-Green", "#71D8BF"), ("S38", "Burgundy", "#AB2556"),
    ("S39", "Yellow Orange", "#ED8B00"), ("S40", "Carnation Pink", "#F1A7DC"),
    ("S41", "Copper", "#9A5516"), ("S42", "Silver", "#A09F9D"),
    ("S43", "Dark Gray", "#767777"), ("S44", "Sky Blue", "#8DC8E8"),
    ("S45", "Medium Turquoise", "#00B2A9"), ("S46", "Bright Green", "#73D33C"),
    ("S47", "Marigold", "#B47E00"), ("S48", "Corn", "#FFC72C"),
    ("S49", "Mulberry Wood", "#72195F"), ("S50", "Mandys Pink", "#FAAA8D"),
    ("S51", "Spring Sun", "#FCFBCD"), ("S52", "Picasso", "#F2F0A1"),
    ("S53", "Blue Enchantress", "#69B3E7"), ("S54", "Light Blue", "#0090DA"),
    ("S55", "Pistachio", "#ADDC91"), ("S56", "Bright Carrot", "#FF6A13"),
    ("S57", "Buccaneer", "#A4493D"), ("S58", "Paprika", "#A50034"),
    ("S59", "Butterfly Bush", "#4A1F87"), ("S60", "Lavender", "#A77BCA"),
    ("S61", "Key Lemon Pie", "#CEDC00"), ("S62", "Green Tea", "#007C58"),
    ("S63", "Metallic Gold", "#4C5914"), ("S64", "Black Rock", "#050849"),
    ("S65", "Canary", "#F3EA5D"), ("S66", "Blaze Orange", "#F4633A"),
    ("S67", "Vanilla", "#F3CFB3"), ("S68", "Tan", "#E1C078"),
    ("S69", "Mine Shaft", "#23282B"), ("S70", "Dark Algae", "#9BBC11"),
    ("S71", "Jade Green", "#00852B"), ("S72", "Light Sea Blue", "#59D5D8"),
    ("S73", "Steel Blue", "#48A9C5"), ("S74", "Azure", "#00AED6"),
    ("S75", "Dark Steel Blue", "#0085AD"), ("S76", "Sea Blue", "#00AEC7"),
    ("S77", "Ghost White", "#EFEFEF"), ("S78", "Ash Gray", "#D1D1D1"),
    ("S79", "Light Gray", "#BBBCBC"), ("S80", "Dark Olive", "#999B30"),
    ("S81", "Deer", "#CDB277"), ("S82", "Clay", "#B58150"),
    ("S83", "Sienna", "#B86125"), ("S84", "Deep Chestnut", "#AA5761"),
    ("S85", "Red Wine", "#42031A"), ("S86", "Goldenrod", "#EAAA00"),
    ("S87", "Coral Red", "#FF6D6A"), ("S88", "Dark Pink", "#DA1884"),
    ("S89", "Charcoal Gray", "#484949"), ("S90", "Pastel Orange", "#FFC56E"),
    ("S91", "Brunswick Green", "#183028"), ("S92", "Dandelion", "#DEB947"),
    ("S93", "Pale Skin", "#DAB698"), ("S94", "Warm Blush", "#F4A999"),
    ("S95", "Salmon", "#EE7D67"), ("S96", "Apricot", "#F08661"),
    ("S97", "Papaya", "#D4722A"), ("S98", "Himalaya Blue", "#64ACDF"),
    ("S99", "Waterfall", "#64C2DC"), ("S100", "Lagoon", "#4F9FB3"),
    ("S101", "Electric Blue", "#3196DD"), ("S102", "Pool Blue", "#1B6CB6"),
    ("S103", "Caribbean Blue", "#083980"), ("S104", "Deep Water", "#0A668B"),
    ("S105", "Petrol Blue", "#085B6E"), ("S106", "Wedgewood Blue", "#004E78"),
    ("S107", "Pond Blue", "#005574"), ("S108", "Seashell Beige", "#CCBE80"),
    ("S109", "Beige", "#A49350"), ("S110", "Beach Beige", "#9E883C"),
    ("S111", "Caffe Latte", "#766C2B"), ("S112", "Oaktree Brown", "#795F26"),
    ("S113", "Khaki", "#BAB8A2"), ("S114", "Light Greengray", "#728C54"),
    ("S115", "Mossy Green", "#7E7C44"), ("S116", "Earth Green", "#64692E"),
    ("S117", "Sage Green", "#4E582C"), ("S118", "Pinetree Green", "#4A5E2D"),
    ("S119", "Frosty Blue", "#71C452"), ("S120", "Polar Mint", "#66CC99"),
    ("S121", "Celadon Green", "#569A83"), ("S122", "Eucalyptus", "#14C25B"),
    ("S123", "Clover Field", "#18A818"), ("S124", "Pooltable Felt", "#04552E"),
    ("S125", "Snake Green", "#136B5A"), ("S126", "Dark Eucalyptus", "#054641"),
    ("S127", "Marshmallow Rose", "#D9B6D6"), ("S128", "Light Grape", "#AD62A4"),
    ("S129", "Rosebud Pink", "#E68CA3"), ("S130", "Fuchsia", "#DE5479"),
    ("S131", "Candy Violet", "#9E82BA"), ("S132", "Flamingo", "#E8416B"),
    ("S133", "Pink Plum", "#B7388F"), ("S134", "Amethyst", "#581F7E"),
    ("S135", "Moonlight Blue", "#8CA3D4"), ("S136", "Summer Rain", "#9A9ACC"),
    ("S137", "Azur Blue", "#5981C1"), ("S138", "Cornflower Blue", "#4166B0"),
    ("S139", "Forget Me Not", "#475FAB"), ("S140", "Indigo", "#374593"),
    ("S141", "Horizon Blue", "#3D56A5"), ("S142", "Cobalt", "#294299"),
    ("S143", "Royal Blue", "#25268A"), ("S144", "Marine", "#1A2F6F"),
    ("S145", "Pale Yellow Moss", "#D3C95D"), ("S146", "Bloodrose Red", "#510918"),
    ("S147", "Spearmint", "#64B39E"), ("S148", "Mocha", "#634338"),
    ("S149", "Creme", "#EDD39E"), ("S150", "Iris Violet", "#6963AB"),
    ("S151", "Forest Green", "#2B3F1F"), ("S152", "Lilac", "#9791C5"),
    ("S153", "Pale Lilac", "#B8BDE0"), ("S154", "Sahara Sand", "#F9C898"),
    ("S155", "Sunkissed Teint", "#C39069"), ("S156", "Steel Grey", "#44505B"),
    ("S157", "Iron Grey", "#3E4955"), ("S158", "Pepper", "#202830"),
    ("S159", "Oslo Gray", "#888B8D"),
]

# 预计算：把色板的 HEX 转成 RGB（画图填色用）
_PALETTE = [(c, n, _hex2rgb(h)) for c, n, h in BEAD_PALETTE]
# 再把 RGB 转成 Lab 颜色空间，存成 numpy 数组（配色匹配用——Lab 距离更接近人眼感受）
_PALETTE_LAB = np.array([skcolor.rgb2lab(np.array(rgb, dtype=float) / 255.0)
                         for _, _, rgb in _PALETTE])  # 形状 (159, 3)


def _quantize(arr: np.ndarray) -> np.ndarray:
    """
    向量化配色：把 (h, w, 3) 的图，每个像素映射到最接近的色板【索引】。
    用 numpy 一次性算完，159 色也不会慢。
    """
    lab = skcolor.rgb2lab(arr.astype(float) / 255.0)        # 整图 RGB→Lab，形状 (h, w, 3)
    flat = lab.reshape(-1, 3)                                # 摊平成 (像素数, 3)，方便批量计算
    # 广播：算每个像素 到 每个色板 的 Lab 距离平方，形状 (像素数, 159)
    dists = np.sum((flat[:, None, :] - _PALETTE_LAB[None, :, :]) ** 2, axis=2)
    # 每个像素取距离最小的那个色板【索引】，再还原成 (h, w) 形状
    return np.argmin(dists, axis=1).reshape(lab.shape[:2])


def _auto_size(img: Image.Image) -> int:
    """根据图片颜色复杂度自动选「长边豆数」（24~48）：颜色少→小图，颜色多→大图。"""
    small = np.array(img.resize((64, 64)).convert("RGB"))    # 缩成 64×64 来估算（转数组）
    quantized = (small // 32) * 32                            # 每通道粗量化到 8 级（先 //32 再 *32）
    n_colors = len({tuple(p) for p in quantized.reshape(-1, 3)})  # 数独立颜色数（集合去重）
    if n_colors <= 8:        # 颜色很少（简单图）
        return 24            # 用小豆板
    if n_colors <= 16:
        return 32
    if n_colors <= 28:
        return 40
    return 48                # 颜色很多（细节多）→ 用大豆板


def _font(size: int):
    """加载系统中文字体（微软雅黑/黑体），加载失败就用 PIL 默认字体。"""
    for p in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):  # 候选字体路径
        if os.path.exists(p):              # 字体文件存在
            try:
                return ImageFont.truetype(p, size)  # 加载指定字号的字体
            except Exception:                       # 加载失败
                pass                                # 继续试下一个候选
    return ImageFont.load_default()        # 都没有就用 PIL 自带的默认字体


def generate_bead_art(image_path: str, size=None) -> str:
    """
    把一张图片转成拼豆图纸（正方形格子 + 色号 + 红网格 + 清单）。
    image_path: 输入图片路径
    size: 长边豆数；不传则自动判断
    返回：材料清单文字（图纸存到 data/outputs/bead_pattern_<输入图名>.png）
    """
    # 1. 打开图片，确定豆板尺寸（长边=size或自动，短边按比例不拉伸）
    img = Image.open(image_path).convert("RGB")  # 打开并转成 RGB（去掉透明通道）
    w0, h0 = img.size                             # 原图的宽、高
    long_side = size if size else _auto_size(img) # 长边豆数（指定就用指定，否则自动）
    if w0 >= h0:                                  # 横图（宽 ≥ 高）
        bw, bh = long_side, max(1, round(long_side * h0 / w0))  # 宽=长边，高按比例缩
    else:                                         # 竖图
        bw, bh = max(1, round(long_side * w0 / h0)), long_side  # 高=长边，宽按比例缩

    # 2. 缩放到豆板尺寸 + 向量化配色
    arr = np.array(img.resize((bw, bh)))  # 缩成 bw×bh（之后每像素 = 1 颗豆），转成数组
    idx = _quantize(arr)                   # 每个格子匹配到色板索引，形状 (bh, bw)

    # 3. 统计每种颜色的用量
    counts = {}                                   # 色板索引 → 数量
    for i in idx.reshape(-1):                     # 遍历所有格子的索引
        counts[int(i)] = counts.get(int(i), 0) + 1  # 计数
    total = bw * bh                               # 总豆数
    n_colors = len(counts)                        # 用了几种颜色
    items = sorted(counts.items(), key=lambda kv: -kv[1])  # 按用量从多到少排序

    # 4. 画图纸：浅灰底 + 正方形色块 + 中间色号 + 红网格
    bead_px = 32  # 每格在图里的像素大小（32px，够写下色号）
    margin = 70   # 上下留白（用来放标题和材料清单）
    pat = Image.new("RGB", (bw * bead_px, bh * bead_px + margin * 2), (244, 244, 244))  # 建浅灰底画布
    d = ImageDraw.Draw(pat)  # 拿到画笔
    oy = margin              # 豆图区域的起始 y（顶部留 margin 给标题）
    f_cell = _font(10)       # 格内色号的字体（10 号）
    for y in range(bh):                    # 逐行
        for x in range(bw):                # 逐列
            code, name, rgb = _PALETTE[int(idx[y, x])]  # 这一格对应的 色号/名称/RGB
            # 画一个正方形色块
            d.rectangle([x * bead_px, oy + y * bead_px,
                         (x + 1) * bead_px, oy + (y + 1) * bead_px], fill=rgb)
            # 算这个颜色的亮度，决定色号用黑字还是白字（保证在底色上看得清）
            lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]  # 亮度（加权公式）
            tc = (0, 0, 0) if lum > 140 else (255, 255, 255)        # 亮色块用黑字，暗色块用白字
            # 在格子正中间写色号（anchor="mm" = 中中对齐，即正中心）
            d.text((x * bead_px + bead_px // 2, oy + y * bead_px + bead_px // 2),
                   code, fill=tc, font=f_cell, anchor="mm")
    # 红色网格线（画在色块之上，把每格分隔开）
    for x in range(bw + 1):  # 竖线（共 bw+1 条）
        d.line([x * bead_px, oy, x * bead_px, oy + bh * bead_px], fill=(210, 80, 80))
    for y in range(bh + 1):  # 横线（共 bh+1 条）
        d.line([0, oy + y * bead_px, bw * bead_px, oy + y * bead_px], fill=(210, 80, 80))
    # 顶部标题：尺寸 / 色数 / 总数
    d.text((12, 16), f"{bw}×{bh}  /  {n_colors} 色  /  共 {total} 颗",
           fill=(40, 40, 40), font=_font(35))
    # 底部材料清单（只列前 14 色，完整清单在返回的文字里）
    txt = "  ".join(f"{_PALETTE[i][0]}×{c}" for i, c in items[:14])
    d.text((12, oy + bh * bead_px + 18), "材料：" + txt, fill=(40, 40, 40), font=_font(35))

    # 5. 保存（文件名带上输入图名，避免多张图互相覆盖）
    os.makedirs("data/outputs", exist_ok=True)  # 确保 outputs 目录存在
    stem = os.path.splitext(os.path.basename(image_path))[0]  # 取输入图名（去扩展名），如 "3.jpg"→"3"
    out_path = os.path.abspath(f"data/outputs/bead_pattern_{stem}.png")  # 拼出输出绝对路径
    pat.save(out_path)  # 保存图纸

    # 6. 返回材料清单文字（给 LLM，它会转述给用户）
    material = "\n".join(f"  · {_PALETTE[i][0]} {_PALETTE[i][1]}：{c} 颗" for i, c in items)  # 完整清单
    print(f"   🔧 [工具执行] generate_bead_art('{image_path}') → 自动尺寸 {bw}×{bh}")
    return (
        f"拼豆图纸已生成：{out_path}\n"
        f"规格：{bw}×{bh} = {total} 颗，共 {n_colors} 种颜色（Artkal-S 真实色号）。\n"
        f"材料清单：\n{material}"
    )


# ---------- 工具说明书（给 LLM 看，决定何时调用、怎么传参）----------
BEAD_TOOL = {
    "type": "function",       # 工具类型：函数
    "function": {
        "name": "generate_bead_art",  # 工具名（LLM 用这个名字调用）
        "description": (                # 告诉 LLM 这个工具干什么、什么时候用
            "把一张本地图片转成拼豆图纸：自动判断尺寸，每个格子是正方形并标注 Artkal 色号，"
            "带红色网格和材料清单（参考 a.jpg 风格）。用户想把图片做成拼豆图纸时调用。"
        ),
        "parameters": {                 # 参数定义（JSON schema 格式）
            "type": "object",
            "properties": {
                "image_path": {         # 必填参数：图片路径
                    "type": "string",
                    "description": "要转换的图片路径，例如 data/3.jpg",
                },
                "size": {               # 可选参数：长边豆数
                    "type": "integer",
                    "description": "长边豆数；不传则根据图片复杂度自动判断（24~48）",
                },
            },
            "required": ["image_path"],  # 只有 image_path 是必填
        },
    },
}


# ---------- 直接运行：对真实图片生成拼豆图纸 ----------
if __name__ == "__main__":                # 只有直接运行本文件时才执行
    IMAGE = "data/3.jpg"                   # 要转换的图片（改成你自己的）
    print(f"开始把 {IMAGE} 转成拼豆图纸（自动尺寸）...\n")
    print(generate_bead_art(IMAGE))        # 调用并打印结果
