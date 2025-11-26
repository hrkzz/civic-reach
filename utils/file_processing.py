import io

import pypdf
from PIL import Image, ImageChops


def get_file_aspect_ratio(file_bytes: bytes, file_type: str) -> str:
    """
    Estimates the aspect ratio of the uploaded document (PDF/Image)
    to optimize the generative AI image output dimensions.
    """
    width = 0
    height = 0
    try:
        if "pdf" in file_type:
            pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            if len(pdf_reader.pages) > 0:
                page = pdf_reader.pages[0]
                width = float(page.mediabox.width)
                height = float(page.mediabox.height)
        elif "image" in file_type:
            image = Image.open(io.BytesIO(file_bytes))
            width, height = image.size
        if width > 0 and height > 0:
            ratio = width / height
            if ratio < 0.85:
                return "3:4"
            elif ratio > 1.15:
                return "4:3"
            else:
                return "1:1"
    except Exception:
        pass
    return "3:4"


def trim_black_borders(img: Image.Image) -> Image.Image:
    """
    Trims solid black borders from an image.
    Creates a difference image against a purely black image to find the bounding box of non-black content.
    """
    # Create a black background image of the same size and mode
    bg = Image.new(img.mode, img.size, (0, 0, 0))
    # Find the difference between the original image and the black background
    diff = ImageChops.difference(img, bg)
    # Get the bounding box of the non-zero regions in the difference image
    bbox = diff.getbbox()
    if bbox:
        # Crop the image to the bounding box
        return img.crop(bbox)
    # If the image is entirely black, return it as is (or handle as error)
    return img


