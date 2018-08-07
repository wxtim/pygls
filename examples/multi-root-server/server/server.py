##########################################################################
# Copyright (c) Open Law Library. All rights reserved.                   #
# See ThirdPartyNotices.txt in the project root for license information. #
##########################################################################
from pygls import lsp
from pygls.ls import LanguageServer


class MultiRootServer(LanguageServer):

    def text_is_valid(self, text='', max_text_len=10):
        '''
            Checks length of the text. Default is 10.
        '''
        diagnostics = []

        if len(text) > max_text_len:
            diagnostics.append(
                lsp.Diagnostic(
                    lsp.Range(
                        lsp.Position(0, 0),
                        lsp.Range(0, max_text_len)
                    ),
                    f"Max number of characters is {max_text_len}",
                    source=type(ls).__name__
                )
            )

        return diagnostics


ls = MultiRootServer()


@ls.command('custom.Command')
def custom_command(ls, params):
    '''
        Commands are registered with required `name` argument
    '''
    ls.workspace.show_message('Command `custom.Command` executed')


@ls.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def doc_did_change(ls, contentChanges=None, textDocument=None, **_kwargs):
    '''
        Validate document
    '''
    # Document is already in our workspace
    doc = ls.workspace.get_document(textDocument['uri'])

    def callback(config):
        max_text_len = config[0].get('maxTextLength', 10)

        diagnostics = ls.text_is_valid(doc.source, max_text_len)

        ls.workspace.publish_diagnostics(
            doc.uri, diagnostics)

    ls.get_configuration({
        'items': [{'scopeUri': doc.uri, 'section': 'pygls'}]
    }, callback)
