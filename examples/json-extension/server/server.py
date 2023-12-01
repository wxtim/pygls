from pathlib import Path
from typing import Optional
import uuid

from cylc.flow.cfgspec.workflow import SPEC
from cylc.flow.scripts.lint import check_cylc_file, parse_checks
from cylc.flow.scripts.validate import wrapped_main as cylc_validate, ValidateOptions

from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION, TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_CLOSE, TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_SAVE, TEXT_DOCUMENT_CODE_ACTION
)
from lsprotocol.types import (
    CompletionItem, CompletionList, CompletionOptions,
    CompletionParams,
    Diagnostic,
    DidChangeTextDocumentParams,
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams, MessageType, Position,
    Range, Registration, RegistrationParams,
    Unregistration, UnregistrationParams,
)
from pygls.server import LanguageServer


class CylcLanguageServer(LanguageServer):
    CMD_COUNT_DOWN_BLOCKING = 'countDownBlocking'
    CMD_COUNT_DOWN_NON_BLOCKING = 'countDownNonBlocking'
    CMD_PROGRESS = 'progress'
    CMD_REGISTER_COMPLETIONS = 'registerCompletions'
    CMD_SHOW_CONFIGURATION_THREAD = 'showConfigurationThread'
    CMD_UNREGISTER_COMPLETIONS = 'unregisterCompletions'

    CONFIGURATION_SECTION = 'cylcServer'

    def __init__(self, *args):
        super().__init__(*args)


cylc_ls = CylcLanguageServer('Cylc Language Server', 'v0.1')


async def _validate(ls, params, lint_only=False):
    """Run Cylc lint & Cylc validate

    n.b: Cylc Validate will only return on issue at a time.
    """
    ls.show_message_log('Validating cylc...')
    text_doc = ls.workspace.get_document(params.text_document.uri)
    source = text_doc.source

    # Run Cylc Lint:
    checks = parse_checks(['style'])
    diagnostics = check_cylc_file(
        source, for_language_server=True, checks=checks
    ) if source else []
    diagnostics = [Diagnostic(**d) for d in diagnostics]

    # Add Cylc Validate diagnostics:
    if not lint_only:
        diagnostics += await _validate_cylc(text_doc.uri)

    ls.publish_diagnostics(text_doc.uri, diagnostics)


async def _validate_cylc(text_doc):
    """Run `cylc validate`
    """
    docpath = str(Path(text_doc.split(':')[1]).parent)
    options = ValidateOptions()
    diagnostics = []
    try:
        await cylc_validate(options, docpath)
    except Exception as exc:
        line = 0
        if hasattr(exc, 'line_num'):
            line = exc.line_num
        d = Diagnostic(
            range=Range(Position(line, 0), Position(line, 10)),
            message=str(exc),
            source='cylc validate'
        )
        diagnostics.append(d)
    return diagnostics


@cylc_ls.feature(TEXT_DOCUMENT_COMPLETION, CompletionOptions(trigger_characters=[',']))
def completions(params: Optional[CompletionParams] = None) -> CompletionList:
    """Returns completion items."""

    # Extract a list of valid cylc settings from the config:
    cylc_completions = list(set([
        i.strip(' []')
        for i in SPEC.tree().split('\n')
        if '<' not in i and '>' not in i
    ]))
    cylc_completions = [
        CompletionItem(label=i) for i in cylc_completions]

    return CompletionList(
        is_incomplete=False,
        items=[
            CompletionItem(label='"'),
            CompletionItem(label='['),
            CompletionItem(label=']'),
        ] +
        cylc_completions[1:]   # not the "flow.cylc"
    )


@cylc_ls.feature(TEXT_DOCUMENT_DID_CHANGE)
async def did_change(ls, params: DidChangeTextDocumentParams):
    """Text document did change notification."""
    await _validate(ls, params)


@cylc_ls.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(server: CylcLanguageServer, params: DidCloseTextDocumentParams):
    """Text document did close notification."""
    server.show_message('Closed Cylc Config')


@cylc_ls.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls, params: DidOpenTextDocumentParams):
    """Text document did open notification."""
    ls.show_message(
        'Opened a Cylc Config\n'
        '[https://cylc.github.io/cylc-doc/stable/html/'
        'reference/config/workflow.html]'
    )
    await _validate(ls, params)


from lsprotocol.types import (
    CodeAction,
    CodeActionContext,
    CodeActionKind,
    CodeActionOptions,
    CodeActionParams,
    CodeActionDisabledType,
    Command,
    Diagnostic,
    Position,
    Range,
    TextDocumentIdentifier,
    WorkspaceEdit,
    TextDocumentEdit,
)


@cylc_ls.feature(
    TEXT_DOCUMENT_CODE_ACTION,
    # CodeActionOptions()
)
def my_action(ls, params: CodeActionParams):
    if params.text_document.uri.endswith('flow.cylc'):
        ls.show_message('top level flow.cylc file')
        validate = True
    else:
        ls.show_message('NOT a top level flow.cylc file')
        validate = False
    return [
        CodeAction(
            title="cylc validate",
            disabled=(
                CodeActionDisabledType(
                    'This action disabled because ...')
                if not validate else None
            ),
            command=Command(
                title="cylc validate",
                command="Validate",
            ),
        ),
        CodeAction(
            title="cylc lint",
            command=Command(
                title="cylc lint",
                command="cylc lint",
            ),
        ),
        CodeAction(
            title="cylc vip",
            disabled=(
                CodeActionDisabledType(
                    'This action disabled because ...')
                if not validate else None
            ),
            command=Command(
                title="cylc vip",
                command="cylc vip",
            ),
        )
    ]



@cylc_ls.command(CylcLanguageServer.CMD_REGISTER_COMPLETIONS)
async def register_completions(ls: CylcLanguageServer, *args):
    """Register completions method on the client."""
    params = RegistrationParams(registrations=[
                Registration(
                    id=str(uuid.uuid4()),
                    method=TEXT_DOCUMENT_COMPLETION,
                    register_options={"triggerCharacters": "[':']"})
             ])
    response = await ls.register_capability_async(params)
    if response is None:
        ls.show_message('Successfully registered completions method')
    else:
        ls.show_message('Error happened during completions registration.',
                        MessageType.Error)


@cylc_ls.command(CylcLanguageServer.CMD_UNREGISTER_COMPLETIONS)
async def unregister_completions(ls: CylcLanguageServer, *args):
    """Unregister completions method on the client."""
    params = UnregistrationParams(unregisterations=[
        Unregistration(id=str(uuid.uuid4()), method=TEXT_DOCUMENT_COMPLETION)
    ])
    response = await ls.unregister_capability_async(params)
    if response is None:
        ls.show_message('Successfully unregistered completions method')
    else:
        ls.show_message('Error happened during completions unregistration.',
                        MessageType.Error)
