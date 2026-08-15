import hashlib
from random import Random
from math import sin, cos, ceil

from PIL import Image
from numpy import array

def generate_spirograph_points(R, r, p, length):
    a = 0.0 # angle parameter (aka steps)
    points = []
    while a < length:
        x = (R - r) * cos(a) + p * cos(((R - r) / r) * a) # x coordinate
        y = (R - r) * sin(a) - p * sin(((R - r) / r) * a) # y coordinate
        points.append((x, y))
        a += 0.01 # This can be adjusted for a more or less detailed spirograph. Smaller values yield more points.
    return points

def scale_points(points, width, height):
    # Calculate min and max for x and y
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)

    # Calculate scaling factors based on the image dimensions and the range of x and y
    # This is done by taking the available width and height (minus some padding) and dividing by the range
    scale_x = (width - 20) / (max_x - min_x)
    scale_y = (height - 20) / (max_y - min_y)

    # Center of the image. Used for distance calculation.
    middle = (width//2, height//2)
    scaled_points = []
    for point in points:
        x = int((point[0] - min_x) * scale_x) + 10 # Take X value, padding correction, apply scale and readd padding
        y = int((point[1] - min_y) * scale_y) + 10 # Take Y value, padding correction, apply scale and readd padding
        distance = ((x - middle[0])**2 + (y - middle[1])**2)**0.5 # pythagorean distance from center
        if 2 <= x < width-2 and 2 <= y < height-2: # Ensure point is within bounds for drawing
            scaled_points.append((x, y, distance))
    return scaled_points

def sha256_lower_long(str):
    acc = 0
    for byte in hashlib.sha256(bytes(str, "utf-8")).digest():
        acc = (acc << 8) | (byte & 0xFF)
    return acc

def spirograph(seed: str, width: int, height: int, length: int) -> Image.Image:
    rng = Random(sha256_lower_long(seed))
    line_color_start = (
        rng.randint(0, 255),
        rng.randint(0, 255),
        rng.randint(0, 255),
    )
    line_color_end = (
        rng.randint(0, 255),
        rng.randint(0, 255),
        rng.randint(0, 255),
    )
    colors = []
    for i in range(100):
        ratio = i / 99
        r = int(line_color_start[0] * (1 - ratio) + line_color_end[0] * ratio)
        g = int(line_color_start[1] * (1 - ratio) + line_color_end[1] * ratio)
        b = int(line_color_start[2] * (1 - ratio) + line_color_end[2] * ratio)
        colors.append((r, g, b))
    img_array = array(
        [[(0, 0, 0) for _ in range(height)] for _ in range(width)], dtype="uint8"
    )
    R = rng.randint(50, 150)
    r = rng.randint(10, 50)
    p = rng.randint(10, 50)
    points = generate_spirograph_points(R, r, p, length)
    scaled_points = scale_points(points, width, height)
    min_distance = min(point[2] for point in scaled_points)
    max_distance = max(point[2] for point in scaled_points)
    scale_distance = 99 / (max_distance - min_distance) # Scaling between 0 and 99 for color indexing
    for point in scaled_points:
        x = point[0]
        y = point[1]
        color = ceil((point[2] - min_distance) * scale_distance) - 1 # -1 to convert to 0-99 index. Ceil and then -1 ensures max_distance maps to 99
        img_array[x-2:x+2, y-2:y+2] = colors[color]
    return Image.fromarray(img_array, "RGB")
