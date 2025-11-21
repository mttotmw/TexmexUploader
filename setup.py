from setuptools import setup, find_packages
import os

version_path = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    "freecad", "Texmex_Uploader", "version.py"
)

with open(version_path) as fp:
    exec(fp.read())

setup(
    name="freecad.Texmex_Uploader",
    version=str(__version__),
    packages=[
        "freecad",
        "freecad.Texmex_Uploader"
    ],
    package_data={
        "freecad.Texmex_Uploader": [
            "Resources/Icons/*.svg",
            "Resources/*.png",
            "*.ui",
            "*.qrc",
        ]
    },
    maintainer="Jorge Guadalupe Ventura Lopez",
    maintainer_email="mantenimiento@tmw.mx",
    url="https://github.com/mttotmw/TexmexUploader",
    description=(
        "Workbench corporativo de Texmex Weavers diseñado para integrar FreeCAD "
        "con las herramientas digitales internas del área de Mantenimiento."
    ),
    include_package_data=True,
)
