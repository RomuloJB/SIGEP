---
name: commit-padrao
description: Use sempre que for escrever a mensagem de um commit neste projeto — gera mensagens no padrão Conventional Commits, com resumo no imperativo e um corpo curto que descreve o que foi implementado, nunca apenas um rótulo genérico como "fix" ou "ajustes".
allowed-tools: Bash(git diff *), Bash(git status *), Bash(git log *)
---

## Mudanças pendentes

Antes de escrever a mensagem, rode e leia a saída (o Cursor não expande `!comando`):

```bash
git status
git diff --cached
git log -5 --oneline
```

Se não houver nada staged, informe isso e sugira `git add` — não invente mensagem.

O `git log -5` serve só para contexto do projeto (convenções de escopo, linguagem usada).
Não copie o formato de commits anteriores se eles forem genéricos — a mensagem gerada
segue as regras abaixo independentemente do estilo do histórico.

## Instruções

Escreva a mensagem de commit para o diff staged seguindo estas regras, sem exceção:

1. **Primeira linha**: `tipo(escopo): resumo no imperativo`, até 72 caracteres, sem ponto
   final. Tipos válidos: feat, fix, docs, style, refactor, perf, test, build, ci, chore.
2. **Linha em branco** depois do resumo.
3. **Corpo obrigatório se o diff tocar mais de um arquivo E passar de ~15 linhas no total**:
   2 a 5 linhas (ou bullets) descrevendo em termos concretos o que foi implementado —
   nomeie a função, o modelo, a rota ou o comportamento que mudou. Nunca escreva
   "ajustes diversos", "melhorias" ou repita o resumo com outras palavras.
4. **Exceção ao corpo obrigatório**: se a mudança for autoexplicativa pelo resumo
   (ex: corrigir typo, atualizar link, bump de versão de dependência), o corpo pode
   ser omitido mesmo passando de 15 linhas ou tocando vários arquivos.
5. Se o diff misturar mudanças sem relação entre si, não invente uma mensagem que
   cubra as duas — avise o usuário e sugira separar em dois commits.
6. Nunca descreva algo que não está no diff mostrado acima.
7. Se o diff estiver vazio, informe que não há mudanças staged (sugira `git add`)
   em vez de gerar uma mensagem genérica.

O commit só está correto se o `git log -1` mostrar o resumo **e** o corpo (quando
exigido pela regra 3). Título sozinho, quando um corpo é exigido, não atende esta skill.

## O que o corpo precisa conter

O corpo responde "o que mudou no código?", não "qual é o tema do commit".

- Cite nomes que aparecem no diff: função, classe, rota, template, teste.
- Prefira bullets se houver mais de uma mudança concreta.
- Proibido: reescrever a primeira linha com sinônimos ("adiciona o pipeline", "implementa a funcionalidade", "inclui melhorias").

### Ruim (parafraseia o título — rejeitar)

```
feat(app): implementar analisador Flask de commits do GitHub

Adiciona o pipeline de validação, clone e extração, o relatório
com Plotly, os testes e o README.
```

### Bom (nomeia o que o diff realmente criou)

```
feat(app): implementar analisador Flask de commits do GitHub

Cria Commit, FileChange e ReportData em models/commit.py.
Implementa parse_conventional_commit, parse_github_url,
clone_repository, extract_commits, build_report e cleanup_repo.
A rota POST /analisar orquestra o pipeline e renderiza report.html.
```
