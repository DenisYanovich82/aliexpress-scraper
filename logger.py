class AliexpressLogPrinter:
    instance = None
    logs = None

    def __init__(self, text: str):
        if text is not None:
            if not AliexpressLogPrinter.instance:
                AliexpressLogPrinter.instance = AliexpressLogPrinter(None)
                AliexpressLogPrinter.instance.logs = []
            print(text)
            AliexpressLogPrinter.instance.logs.append(text + "\n")

    @staticmethod
    def export(filename):
        with open(filename, 'w+') as logfile:
            logfile.writelines(AliexpressLogPrinter.instance.logs)
