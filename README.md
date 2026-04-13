# 🎵 Album Organizer 4.0 (Prioridade Local)

**Album Organizer** é um script em Python robusto, desenvolvido para colecionadores que possuem bibliotecas de música digital extensas e desejam uma organização impecável sem perder a sua curadoria manual.

Criado por: **Carlos Eduardo G. Ribeiro** | Github: [@Kkrloz](https://github.com/Kkrloz)

---

## ✨ Diferenciais da Versão 4.0

Diferente de outros organizadores automáticos que confiam cegamente em bases de dados online (muitas vezes trazendo anos de remasterizações ou nomes em outros idiomas), este script foi desenhado com a filosofia **"Local First"**:

1.  **Respeito à Curadoria:** Se a sua pasta já possui um ano (ex: `1980 - Making Movies`), o script mantém esse ano em vez de usar datas de reedições da internet.
2.  **Limpeza Cirúrgica de Faixas:** Remove números duplicados em títulos de músicas (ex: transforma `01. 01 Song.mp3` em `01. Song.mp3`).
3.  **Inteligência para Álbuns Homônimos:** Detecta quando o álbum tem o mesmo nome da banda (ex: *Rage Against The Machine*) e evita deleções acidentais de metadados.
4.  **Tratamento de Prefixos:** Remove automaticamente anos entre parênteses no início de pastas (ex: `(1983) Cargo` vira apenas `Cargo` nas tags internas).
5.  **Compatibilidade Moderna:** Totalmente testado em **Python 3.14** (Fedora) e sistemas Linux modernos.

---

## 🚀 Funcionalidades

-   **Padronização de Pastas:** Renomeia álbuns para `Nome do Álbum (Ano)`.
-   **Tags ID3 Automáticas:** Injeta Artista, Álbum, Ano e Número da Faixa permanentemente nos arquivos.
-   **Download de Capas:** Baixa `cover.jpg` de alta qualidade via MusicBrainz, iTunes ou Deezer.
-   **Geração de Playlists:** Cria arquivos `.m3u` para cada álbum processado.
-   **Modo de Simulação (Seguro):** Flag `--dry-run` para prever todas as mudanças antes de aplicá-las.

---

## 🛠️ Instalação e Requisitos

O script utiliza a biblioteca `mutagen` para editar as tags ID3 dos arquivos de áudio.

### Instalando as Dependências
No seu terminal, execute o comando correspondente ao seu sistema:

```bash
# No Fedora/CentOS/RHEL
sudo dnf install python3-mutagen

# No Ubuntu/Debian/Mint
sudo apt install python3-mutagen

# Via PIP (Qualquer sistema)
pip install mutagen
