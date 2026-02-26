"""Implementação de ChatUI com interface gráfica Tkinter.

A janela corre em uma thread dedicada (`"tk-gui"`) enquanto o `ChatClient`
roda na thread principal. A comunicação entre as duas é feita exclusivamente
por meio de `queue.Queue` e `threading.Event`, sem acesso direto a widgets
fora da thread Tk.
"""

import contextlib
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, scrolledtext, ttk

from net.application.chat.codec import Message
from net.application.chat.file import FileMessage
from net.application.chat.system import SystemMessage
from net.application.chat.text import TextMessage
from net.stack.factory import DOWNLOADS_DIR, ensure_downloads_dir

# Sufixos reconhecidos nas mensagens de sistema para manter a lista de usuários.
JOINED_SUFFIX = " entrou no chat."
LEFT_SUFFIX = " saiu do chat."


class GUI:
    """Implementação de `UI` com interface gráfica Tkinter."""

    # Fontes usadas em toda a janela.
    FONT_MAIN: tuple[str, int] = ("Helvetica", 10)
    FONT_BOLD: tuple[str, int, str] = ("Helvetica", 10, "bold")

    # Quadros do spinner de conexao (ASCII puro - tkinter nao lida bem com
    # braille e outros simbolos unicode fora do BMP em todas as plataformas).
    SPINNER: tuple[str, ...] = ("|", "/", "-", "\\")

    def __init__(self) -> None:
        """Inicializa o estado interno sem criar nenhum widget Tk."""
        self.name: str = ""
        self.input_queue: queue.Queue[str | Path | None] = queue.Queue()

        self.root: tk.Tk | None = None
        self.text: scrolledtext.ScrolledText | None = None
        self.entry: ttk.Entry | None = None
        self.status_var: tk.StringVar | None = None
        self.users: tk.Listbox | None = None
        self.send_button: ttk.Button | None = None
        self.file_button: ttk.Button | None = None

        self.user_list: list[str] = []
        self.spinner_running: bool = False
        self.spinner_index: int = 0

    def show_connecting(self, name: str) -> None:
        """Constrói a janela Tk imediatamente com spinner de conexão.

        Lança a thread Tk e bloqueia até a janela estar visível, mas os
        controles de entrada permanecem desabilitados até `show_connected`
        ser chamado.

        Args:
            name: Nome do usuário local. Usado no título da janela.
        """
        self.name = name
        ready = threading.Event()
        threading.Thread(
            target=self._run_tk,
            args=(ready,),
            daemon=True,
            name="tk-gui",
        ).start()
        ready.wait()

    def show_connected(self, name: str) -> None:
        """Habilita os controles de chat após a conexão ser estabelecida.

        Pode ser chamado a partir de qualquer thread.

        Args:
            name: Nome do usuário (mantido por compatibilidade com o protocolo).
        """
        self._schedule(self._enable_chat)

    def show_message(self, message: Message, at: datetime) -> None:
        """Exibe a mensagem recebida na área de chat de forma thread-safe.

        Mensagens de texto são exibidas diretamente. Arquivos são salvos em
        thread separada (não bloqueia a recepção). Mensagens de sistema também
        atualizam a lista de participantes.

        Args:
            message: A mensagem a exibir.
            at: Instante em que a mensagem foi recebida.
        """
        timestamp = at.strftime("%H:%M:%S")

        if isinstance(message, TextMessage):
            text = f"[{timestamp}] {message.sender}: {message.content}"
            self._schedule(lambda: self._append(text, tag="other"))

        elif isinstance(message, FileMessage):
            threading.Thread(
                target=self._save_file,
                args=(message, timestamp),
                daemon=True,
            ).start()

        else:
            text = f"[{timestamp}] {message.content}"
            self._schedule(lambda: self._show_system(text, message))

    def show_server_disconnected(self) -> None:
        """Exibe aviso de desconexão, enfileira `None` e fecha a janela."""
        self._schedule(
            lambda: self._append(
                "[SISTEMA] Conexão encerrada pelo servidor.", tag="system"
            )
        )
        self.input_queue.put(None)
        self._schedule(self._close_window)

    def read_input(self) -> str | Path | None:
        """Bloqueia a thread do `ChatClient` até o usuário interagir.

        Returns:
            Uma `str` com o texto a enviar, um `Path` com o arquivo a
            transferir, ou `None` para encerrar a sessão.
        """
        return self.input_queue.get()

    # --- Ciclo de Vida ---

    def _run_tk(self, ready: threading.Event) -> None:
        """Constrói todos os widgets e entra no mainloop do Tk.

        Chamado na thread `"tk-gui"`. Sinaliza `ready` logo antes de
        iniciar o mainloop, garantindo que `show_connected()` só retorne
        depois que a janela estiver visível.

        Args:
            ready: Evento sinalizado quando a janela está pronta.
        """
        self.root = tk.Tk()
        self.root.title(f"Chat — {self.name}")
        self.root.geometry("780x520")
        self.root.minsize(500, 360)

        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.spinner_running = True
        self._tick_spinner()
        ready.set()
        self.root.mainloop()

    def _build_layout(self) -> None:
        """Constrói o layout completo da janela dentro da thread Tk.

        Divide a janela em painel esquerdo (mensagens + entrada) e painel
        direito (lista de participantes), usando um `PanedWindow` redimensionável.
        """
        assert self.root is not None

        paned = tk.PanedWindow(self.root, sashrelief=tk.RAISED)
        paned.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(paned)
        right = tk.Frame(paned, width=170)
        paned.add(left)  # pyright: ignore[reportUnknownMemberType]
        paned.add(right)  # pyright: ignore[reportUnknownMemberType]

        self._build_message_area(left)
        self._build_input_bar(left)
        self._build_status_bar()
        self._build_user_list(right)

    def _build_message_area(self, parent: tk.Frame) -> None:
        """Cria a área de texto com rolagem onde as mensagens são exibidas.

        Configura três tags de formatação:
        - `"you"` — mensagens enviadas pelo próprio usuário (vermelho escuro).
        - `"other"` — mensagens recebidas (azul).
        - `"system"` — eventos do sistema (cinza).

        Args:
            parent: Frame pai onde o widget será empacotado.
        """
        self.text = scrolledtext.ScrolledText(
            parent,
            state=tk.DISABLED,
            wrap=tk.WORD,
            font=self.FONT_MAIN,
        )
        self.text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))
        self.text.tag_config("you", foreground="#e75631", font=self.FONT_BOLD)
        self.text.tag_config("other", foreground="#1a73e8")
        self.text.tag_config("system", foreground="#6c757d", font=self.FONT_BOLD)

    def _build_input_bar(self, parent: tk.Frame) -> None:
        """Cria a barra de entrada de texto e os botões Enviar e Arquivo.

        `<Return>` no campo de texto aciona `_on_send()`. O botão
        `"Arquivo…"` abre um diálogo de seleção de arquivo.

        Args:
            parent: Frame pai onde a barra será empacotada.
        """
        bar = tk.Frame(parent)
        bar.pack(fill=tk.X, padx=8, pady=8)

        self.entry = ttk.Entry(bar, font=self.FONT_MAIN, state=tk.DISABLED)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.entry.bind("<Return>", lambda _e: self._on_send())

        self.send_button = ttk.Button(
            bar, text="Enviar", command=self._on_send, state=tk.DISABLED
        )
        self.send_button.pack(side=tk.LEFT)
        self.file_button = ttk.Button(
            bar, text="Arquivo...", command=self._on_file, state=tk.DISABLED
        )
        self.file_button.pack(side=tk.LEFT, padx=(6, 0))

    def _build_status_bar(self) -> None:
        """Cria a barra de status na parte inferior da janela principal."""
        assert self.root is not None
        self.status_var = tk.StringVar(value="")
        ttk.Label(self.root, textvariable=self.status_var, anchor="w").pack(
            fill=tk.X, padx=8, pady=(0, 4)
        )

    def _build_user_list(self, parent: tk.Frame) -> None:
        """Cria o painel lateral com a lista de participantes conectados.

        O próprio usuário é adicionado imediatamente após a criação.

        Args:
            parent: Frame pai (painel direito) onde a lista será empacotada.
        """
        ttk.Label(parent, text="Usuários", font=self.FONT_BOLD).pack(
            anchor="nw", padx=6, pady=(6, 0)
        )
        self.users = tk.Listbox(parent, font=self.FONT_MAIN)
        self.users.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    # --- Spinner de conexão (somente thread Tk) ---

    def _tick_spinner(self) -> None:
        """Avança o spinner na barra de status a cada 100 ms."""
        if not self.spinner_running or self.root is None or self.status_var is None:
            return
        character = self.SPINNER[self.spinner_index % len(self.SPINNER)]
        self.spinner_index += 1
        self.status_var.set(f"{character}  Conectando ao servidor...")
        self.root.after(100, self._tick_spinner)

    def _enable_chat(self) -> None:
        """Encerra o spinner e habilita os controles após conexão confirmada.

        Executado na thread Tk via `_schedule`.
        """
        self.spinner_running = False
        if self.status_var is not None:
            self.status_var.set("Conectado")
        if self.entry is not None:
            self.entry.configure(state=tk.NORMAL)
            self.entry.focus()
        if self.send_button is not None:
            self.send_button.configure(state=tk.NORMAL)
        if self.file_button is not None:
            self.file_button.configure(state=tk.NORMAL)
        self._add_user(self.name)

    # --- Manipuladores de eventos (somente thread Tk) ---

    def _on_send(self) -> None:
        """Lê o texto do campo de entrada e o enfileira para envio."""
        if self.entry is None:
            return
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, tk.END)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._append(f"[{timestamp}] Você: {text}", tag="you")
        self.input_queue.put(text)

    def _on_file(self) -> None:
        """Abre diálogo de seleção de arquivo e enfileira o `Path` escolhido.

        Exibe uma confirmação na área de chat com nome e tamanho do arquivo.
        Descarta silenciosamente se o usuário cancelar o diálogo.
        """
        path_str = filedialog.askopenfilename()
        if not path_str:
            return
        path = Path(path_str)
        if not path.is_file():
            self._append(f"[SISTEMA] Arquivo não encontrado: {path}", tag="system")
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._append(
            f"[{timestamp}] Enviando: {path.name} ({path.stat().st_size} B)…",
            tag="system",
        )
        self.input_queue.put(path)

    def _on_close(self) -> None:
        """Trata o fechamento da janela pelo usuário.

        Enfileira `None` para que `read_input()` desbloqueie e encerre a
        sessão normalmente antes de destruir a janela.
        """
        self.input_queue.put(None)
        self._close_window()

    # --- Manipulação de mensagens recebidas (agendadas na thread Tk) ---

    def _append(self, text: str, tag: str | None = None) -> None:
        """Insere uma linha de texto na área de mensagens.

        Args:
            text: Linha de texto a inserir.
            tag: Tag de formatação (`"you"`, `"other"` ou `"system"`).
                 Nenhuma formatação especial se `None`.
        """
        if self.text is None:
            return
        self.text.configure(state=tk.NORMAL)
        self.text.insert(tk.END, text + "\n", tag or "")
        self.text.see(tk.END)
        self.text.configure(state=tk.DISABLED)

    def _show_system(self, text: str, message: SystemMessage) -> None:
        """Exibe uma mensagem de sistema e sincroniza a lista de participantes.

        Args:
            text: Texto já formatado para exibição.
            message: Mensagem de sistema original, usada para detectar
                entradas e saídas de usuários.
        """
        self._append(text, tag="system")
        self._sync_user_list(message)

    def _sync_user_list(self, message: SystemMessage) -> None:
        """Atualiza a lista de participantes com base no conteúdo da mensagem.

        Reconhece os sufixos `JOINED_SUFFIX` e `LEFT_SUFFIX` para
        adicionar ou remover o participante correspondente.

        Args:
            message: Mensagem de sistema a interpretar.
        """
        content = message.content
        if content.endswith(JOINED_SUFFIX):
            self._add_user(content[: -len(JOINED_SUFFIX)])

        elif content.endswith(LEFT_SUFFIX):
            self._remove_user(content[: -len(LEFT_SUFFIX)])

    def _add_user(self, name: str) -> None:
        """Adiciona um participante à lista, ignorando duplicatas.

        Args:
            name: Nome do participante a adicionar.
        """
        if self.users is None or name in self.user_list:
            return
        self.user_list.append(name)
        self.users.insert(tk.END, name)

    def _remove_user(self, name: str) -> None:
        """Remove um participante da lista, ignorando nomes desconhecidos.

        Args:
            name: Nome do participante a remover.
        """
        if self.users is None or name not in self.user_list:
            return
        index = self.user_list.index(name)
        self.user_list.remove(name)
        self.users.delete(index)

    def _close_window(self) -> None:
        """Encerra o mainloop do Tk e destrói a janela de forma segura.

        Não faz nada se a janela já foi destruída (idempotente).
        """
        if self.root is not None:
            try:
                self.root.quit()
                self.root.destroy()

            except Exception:
                pass
            self.root = None

    # --- Agendamento ---

    def _schedule(self, function: Callable[[], object]) -> None:
        """Agenda a execução de `function` na thread do Tk.

        Args:
            function: Callable sem argumentos a executar na thread Tk.
        """
        if self.root is not None:
            with contextlib.suppress(Exception):
                self.root.after(0, function)
                return
        with contextlib.suppress(Exception):
            function()

    # --- Salvamento de arquivos recebidos ---

    def _save_file(self, message: FileMessage, timestamp: str) -> None:
        """Salva o arquivo recebido em `downloads/<destinatário>/<nome>`.

        Executado em thread daemon para não bloquear o loop de recepção.
        Após salvar, agenda a exibição de uma confirmação na área de chat.

        Args:
            message: Mensagem de arquivo com conteúdo e metadados.
            timestamp: Horário formatado da recepção (`HH:MM:SS`).
        """
        ensure_downloads_dir()
        destination = DOWNLOADS_DIR / message.recipient / message.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(message.data)
        self._schedule(
            lambda: self._append(
                f"[{timestamp}] {message.sender} enviou arquivo: "
                f"{message.name} ({message.size} B) — salvo em {destination.resolve()}",
                tag="system",
            )
        )
