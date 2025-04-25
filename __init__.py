def classFactory(iface):
    from .plugin import MyPlugin
    return MyPlugin(iface)