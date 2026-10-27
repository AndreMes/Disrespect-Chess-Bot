# Disrespect Bot

Base local e testável para um bot de xadrez do Lichess. Esta primeira versão
joga partidas locais usando Stockfish e um repertório de aberturas definido pelo
usuário; a integração com a Bot API fica isolada para a próxima etapa.

## Princípios do MVP

- O repertório é exclusivamente manual: nenhuma abertura é inventada.
- Uma linha só é usada enquanto permanecer legal e compatível com a posição.
- Fora do repertório, o melhor lance do Stockfish é o padrão.
- Segredos não são armazenados; a futura integração lerá `LICHESS_BOT_TOKEN`.

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Baixe o Stockfish e informe seu caminho em `config.yaml` (ou defina
`STOCKFISH_PATH`). No Windows, use o ZIP universal x86-64 do site oficial;
extraia-o, por exemplo, em `tools/stockfish/` (essa cópia local é ignorada pelo
Git). O executável termina em `.exe`.

## Testes e partida local

```powershell
python -m pytest -q
python -m disrespect_bot.local_game --config config.yaml --white bot --depth 10
```

Os PGNs e eventos em JSON são gravados em `logs/`.

## Lichess (teste controlado)

O cliente usa exclusivamente a Bot API oficial. Antes de iniciá-lo, crie uma
conta de bot separada, gere um token com permissão `bot:play` e mantenha-o fora
do repositório. Em `config.yaml`, habilite `lichess.enabled`, habilite
`accept_challenges` e liste apenas o seu usuário em `allowed_challengers`.

```powershell
$env:LICHESS_BOT_TOKEN = "cole-o-token-somente-nesta-sessao"
python -m disrespect_bot.lichess --config config.yaml
```

O modo padrão é seguro: o cliente não inicia nem aceita desafios enquanto essas
opções não forem ativadas deliberadamente.
