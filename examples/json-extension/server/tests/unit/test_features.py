############################################################################
# Copyright(c) Open Law Library. All rights reserved.                      #
# See ThirdPartyNotices.txt in the project root for additional notices.    #
#                                                                          #
# Licensed under the Apache License, Version 2.0 (the "License")           #
# you may not use this file except in compliance with the License.         #
# You may obtain a copy of the License at                                  #
#                                                                          #
#     http: // www.apache.org/licenses/LICENSE-2.0                         #
#                                                                          #
# Unless required by applicable law or agreed to in writing, software      #
# distributed under the License is distributed on an "AS IS" BASIS,        #
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. #
# See the License for the specific language governing permissions and      #
# limitations under the License.                                           #
############################################################################
import io

import pytest
from mock import Mock
from lsprotocol.types import (DidCloseTextDocumentParams,
                              DidOpenTextDocumentParams, TextDocumentIdentifier,
                              TextDocumentItem)
from pygls.server import StdOutTransportAdapter
from pygls.workspace import Document, Workspace

from ...server import (
    CylcLanguageServer,
    completions,
    did_close,
    did_open,
)


fake_document_uri = 'file://flow.cylc'
fake_document_content = '    [meta]'
fake_document = Document(fake_document_uri, fake_document_content)


server = CylcLanguageServer('test-cylc-server', 'v1')
server.publish_diagnostics = Mock()
server.show_message = Mock()
server.show_message_log = Mock()
server.lsp.workspace = Workspace('', None)
server.lsp._send_only_body = True
server.workspace.get_document = Mock(return_value=fake_document)


def _reset_mocks(stdin=None, stdout=None):

    stdin = stdin or io.StringIO()
    stdout = stdout or io.StringIO()

    server.lsp.transport = StdOutTransportAdapter(stdin, stdout)
    server.publish_diagnostics.reset_mock()
    server.show_message.reset_mock()
    server.show_message_log.reset_mock()


def test_completions():
    completion_list = completions()
    labels = [i.label for i in completion_list.items]

    assert '"' in labels
    assert '[' in labels
    assert ']' in labels


def test_did_close():
    _reset_mocks()

    params = DidCloseTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=fake_document_uri))

    did_close(server, params)

    # Check if show message is called
    server.show_message.assert_called_once()


@pytest.mark.asyncio
async def test_did_open():
    _reset_mocks()

    params = DidOpenTextDocumentParams(
        text_document=TextDocumentItem(uri=fake_document_uri,
                                       language_id='cylc',
                                       version=1,
                                       text=fake_document_content))

    await did_open(server, params)

    # Check publish diagnostics is called
    server.publish_diagnostics.assert_called_once()

    # Check publish diagnostics args message
    assert (
        'Top level section'
        in server.publish_diagnostics.call_args.args[1][0].message
    )

    # Check other methods are called
    server.show_message.assert_called_once()
    server.show_message_log.assert_called_once()
