""" KvLang language server support for the language of Kivy. Current module is responsible
    for handling requests, notification from client or response/notification
    from server to client. Server work in stdin/stdout comunication using
    specification included in version 3.x of the language server protocol. """
from kvls.message import RequestMessage, ResponseMessage, NotificationMessage
from kvls.kvlint import KvLint
from kvls.logger import Logger

# Disable logger in released code.
Logger.DISABLED = True

class KvLangServer(object):
    """ Class responsible for managing Language Server Procedures """
    SHUTDOWN = 6
    RUNNING = 8
    EXIT_SUCCESS = 0
    EXIT_ERROR = 1
    OFF_LINE = 4

    def __init__(self, stdin, stdout):
        self.logger = Logger()
        self.reader = stdin
        self.writer = stdout
        self.server_status = self.OFF_LINE
        self.procedures = {"initialize": self.initialize,
                           "initialized": self.initialized,
                           "textDocument/didSave": self.did_save,
                           "textDocument/didOpen": self.did_open,
                           "textDocument/didClose": self.did_close,
                           "shutdown": self.shutdown,
                           "exit": self.exit}

    def send(self, response):
        """ Send message to the client """
        result = response.build()
        self.writer.write(result)
        self.writer.flush()
        self.logger.log(Logger.INFO, result)

    def handle(self, content):
        """ Start hadling input from stdin """
        request = RequestMessage()
        request.content_length(content)
        # It is content type
        content_type_or_eol = self.reader.readline()
        if request.content_type(content_type_or_eol):
            # Read also new line
            self.reader.readline()
        request.content(self.reader.read(request.length))
        # Message is rebuild again for logger only.
        # Remove it will not cause any problems
        self.logger.log(Logger.INFO, request.build())
        # Start handling requested method from client
        # Message is ready to use
        self.procedures.get(request.method(), self.default)(request)

    def run(self):
        """ Main loop for processing input from stdin """
        self.server_status = self.RUNNING
        while True:
            if self.server_status == self.EXIT_SUCCESS:
                return self.EXIT_SUCCESS
            elif self.server_status == self.EXIT_ERROR:
                return self.EXIT_ERROR
            else:
                line_with_content = self.reader.readline()
                self.handle(line_with_content)

    def initialize(self, request):
        """ Handle Initialize Request"""
        response = ResponseMessage()
        response.content({'capabilities': {'textDocumentSync': {'openClose': True,
                                                                'change': 0,
                                                                'willSave': False,
                                                                'willSaveWaitUntil': False,
                                                                'save': {'includeText': True}}
                                          }}, True, request.request_id())
        self.send(response)

    def initialized(self, _):
        """ Handle Initialized Notification  """
        pass

    def did_save(self, request):
        """ Handle DidSaveTextDocument Notification """
        lint = KvLint()
        result = lint.parser_exception(request.params()["text"])
        if result is not None:
            diagnostic = {'range': {'start': {'line': result.start['line'],
                                              'character': result.start['character']},
                                    'end': {'line': result.end['line'],
                                            'character': result.end['character']}},
                          'severity': result.severity,
                          'code': result.code,
                          'source': result.source,
                          'message': result.message}
            notification = NotificationMessage()
            notification.content({'uri': request.params()["textDocument"]["uri"],
                                  'diagnostics': [diagnostic]}, 'textDocument/publishDiagnostics')
            self.send(notification)
        else:
            # Clear diagnostic
            notification = NotificationMessage()
            notification.content({'uri': request.params()["textDocument"]["uri"],
                                  'diagnostics': []}, 'textDocument/publishDiagnostics')
            self.send(notification)

    def did_open(self, request):
        """ Handle DidOpenTextDocumentParams Notification """
        lint = KvLint()
        result = lint.parser_exception(request.params()["textDocument"]["text"])
        if result is not None:
            diagnostic = {'range': {'start': {'line': result.start['line'],
                                              'character': result.start['character']},
                                    'end': {'line': result.end['line'],
                                            'character': result.end['character']}},
                          'severity': result.severity,
                          'code': result.code,
                          'source': result.source,
                          'message': result.message}
            notification = NotificationMessage()
            notification.content({'uri': request.params()["textDocument"]["uri"],
                                  'diagnostics': [diagnostic]}, 'textDocument/publishDiagnostics')
            self.send(notification)
        else:
            # Clear diagnostic
            notification = NotificationMessage()
            notification.content({'uri': request.params()["textDocument"]["uri"],
                                  'diagnostics': []}, 'textDocument/publishDiagnostics')
            self.send(notification)

    def did_close(self, request):
        """ Handle DidCloseTextDocumentParams Notification """
        # Clear diagnostic
        notification = NotificationMessage()
        notification.content({'uri': request.params()["textDocument"]["uri"],
                              'diagnostics': []}, 'textDocument/publishDiagnostics')
        self.send(notification)

    def default(self, request):
        """ Handle unknown method which do not exist in procedures"""
        self.logger.log(Logger.INFO, "Server do not support request with method='{}'". \
                        format(request.method()))
        raise Exception("Server do not support request with method='{}'".format(request.method()))

    def shutdown(self, request):
        """ Handle Shutdown Request """
        response = ResponseMessage()
        response.content({}, True, request.request_id())
        self.server_status = self.SHUTDOWN
        self.send(response)

    def exit(self, _):
        """ Handle Exit Notification """
        if self.server_status == self.SHUTDOWN:
            self.server_status = self.EXIT_SUCCESS
        else:
            self.server_status = self.EXIT_ERROR
        self.logger.log(Logger.INFO,
                        "Server exit with server_status={}".format(self.server_status))