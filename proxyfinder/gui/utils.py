import os.path

GUI_PATH = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(GUI_PATH, "user_settings.ini")
LOCALE_PATH = os.path.join(GUI_PATH, "locale", "release")
IMAGES_PATH = os.path.join(GUI_PATH, "images")

LANGUAGES = {
    "en_US": "English",
    "it_IT": "Italiano",
    }


def image(filename):
    """Obtain absolute path for the images

    Args:
        filename (str): image filename

    Returns:
        str: absolute path for the image
    """
    return os.path.join(IMAGES_PATH, filename)
