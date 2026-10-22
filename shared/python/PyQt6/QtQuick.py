# Anki only uses QtQuick to pick the graphics API for Qt WebEngine.
import enum


class QSGRendererInterface:
    class GraphicsApi(enum.Enum):
        Unknown = 0
        Software = 1
        OpenVG = 2
        OpenGL = 3
        Direct3D11 = 4
        Vulkan = 5
        Metal = 6
        Null = 7
        Direct3D12 = 8


class QQuickWindow:
    _api = QSGRendererInterface.GraphicsApi.Metal

    @staticmethod
    def setGraphicsApi(api):
        QQuickWindow._api = api

    @staticmethod
    def graphicsApi():
        return QQuickWindow._api
