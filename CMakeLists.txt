set(Namespace_SRCS
        freecad/Texmex_Uploader/init_gui.py
        freecad/Texmex_Uploader/__init__.py
        freecad/Texmex_Uploader/my_numpy_function.py
        freecad/Texmex_Uploader/version.py
        freecad/Texmex_Uploader/resources/boxlogo.svg
        freecad/Texmex_Uploader/resources/translations/Texmex_Uploader_es-ES.qm
        freecad/Texmex_Uploader/resources/translations/Texmex_Uploader_es-ES.ts
)

SOURCE_GROUP("" FILES ${Namespace_SRCS})

ADD_CUSTOM_TARGET(SEARCHBAR ALL
        SOURCES ${Namespace_SRCS}
)

fc_copy_sources(SEARCHBAR "${CMAKE_BINARY_DIR}/Mod/TexmexUploader" ${Namespace_SRCS})

INSTALL(
    FILES
        ${Namespace_SRCS}
    DESTINATION
        Mod/SearchBar
)
