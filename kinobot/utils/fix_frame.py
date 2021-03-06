import json
import logging
import subprocess

import cv2
from PIL import Image, ImageChops, ImageStat
from pymediainfo import MediaInfo

logger = logging.getLogger(__name__)


def isBW(imagen):
    hsv = ImageStat.Stat(imagen.convert("HSV"))
    return hsv.mean[1]


# remove black borders if present
def trim(im):
    if isBW(im) < 35:
        return im
    bg = Image.new(im.mode, im.size, im.getpixel((0, 0)))
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff)  # , 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        cropped = im.crop(bbox)
        return cropped


def convert2Pil(c2vI):
    image = cv2.cvtColor(c2vI, cv2.COLOR_BGR2RGB)
    return Image.fromarray(image)


def get_dar(file):
    command = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        file,
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE)
    return json.loads(result.stdout)["streams"][0]["display_aspect_ratio"].split(":")


def center_crop_image(pil_image):
    " Crop if the image is too wide as it doesn't look good on Facebook "
    width, height = pil_image.size
    mean = width / height
    if mean <= 2.25:
        return pil_image
    logger.info("Cropping too wide image")
    new_width = width * (0.8 if mean <= 2.4 else 0.7)
    new_width = width * 0.7
    left = (width - new_width) / 2
    right = (width + new_width) / 2
    bottom = height
    try:
        return pil_image.crop((int(left), 0, int(right), bottom))
    except Exception as e:
        logger.error(e, exc_info=True)
        return pil_image


def needed_fixes(file, frame, check_palette=True):
    logger.info("Checking DAR")
    try:
        logger.info("Using ffprobe")
        f, s = get_dar(file)
        DAR = float(f) / float(s)
    except Exception as e:
        logger.error(e, exc_info=True)
        logger.info("Using mediainfo. This will take a while")
        mi = MediaInfo.parse(file, output="JSON")
        DAR = float(json.loads(mi)["media"]["track"][1]["DisplayAspectRatio"])
    logger.info("Extracted display aspect ratio: {}".format(DAR))
    # fix width
    width, height, lay = frame.shape
    logger.info("Original dimensions: {}*{}".format(width, height))
    fixAspect = DAR / (width / height)
    width = int(width * fixAspect)
    # resize with fixed width (cv2)
    logger.info("Fixed dimensions: {}*{}".format(width, height))
    resized = cv2.resize(frame, (width, height))
    # trim image if black borders are present. Convert to PIL first
    # return the pil image
    pil_image = convert2Pil(resized)
    trim_image = trim(pil_image)
    final_image = center_crop_image(trim_image)
    if check_palette:
        if isBW(final_image) > 35:
            return final_image, True
        else:
            return final_image, False
    return final_image
