"""Gerador de PDFs mínimos e válidos para testes e demonstração do Habilita."""

import hashlib
import uuid


def derivar_uuid_arquivo(tenant_id: str, trabalhador_id: str, documento_id: str) -> str:
    """Gera um UUID v5 determinístico para o nome do arquivo a partir dos identificadores."""
    nome = f"habilita://{tenant_id}/{trabalhador_id}/{documento_id}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, nome))


def calcular_sha256(conteudo: bytes) -> str:
    """Calcula o hash SHA-256 em formato hexadecimal de um conteúdo binário."""
    return hashlib.sha256(conteudo).hexdigest()


def gerar_pdf_ficticio(
    documento_id: str,
    trabalhador_id: str,
    tipo_nome: str,
    valido_ate: str,
    detalhes: str = "",
) -> bytes:
    """Gera um PDF mínimo, sintaticamente válido e estritamente determinístico.

    Contém o carimbo 'DOCUMENTO FICTÍCIO' e informações específicas do documento,
    garantindo que cada documento gere um arquivo binário distinto e com hash único.
    Não utiliza nenhuma dependência externa (apenas recursos nativos de manipulação de bytes).
    """
    stream_lines = [
        "BT",
        "/F1 18 Tf",
        "50 720 Td",
        "(DOCUMENTO FICTICIO - AMBIENTE DE DEMONSTRACAO SST) Tj",
        "/F1 12 Tf",
        "0 -40 Td",
        f"(Documento ID: {documento_id}) Tj",
        "0 -20 Td",
        f"(Trabalhador ID: {trabalhador_id}) Tj",
        "0 -20 Td",
        f"(Tipo de Documento: {tipo_nome}) Tj",
        "0 -20 Td",
        f"(Valido Ate: {valido_ate}) Tj",
    ]
    if detalhes:
        stream_lines.extend(["0 -20 Td", f"(Observacao: {detalhes}) Tj"])
    stream_lines.append("ET\n")

    stream_content = "\n".join(stream_lines).encode("latin-1")
    length = len(stream_content)

    parts: list[bytes] = [b"%PDF-1.4\n"]
    offsets: list[int] = []

    # Objeto 1: Catalog
    offsets.append(sum(len(p) for p in parts))
    parts.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

    # Objeto 2: Pages
    offsets.append(sum(len(p) for p in parts))
    parts.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")

    # Objeto 3: Page
    offsets.append(sum(len(p) for p in parts))
    parts.append(
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n"
        b"endobj\n"
    )

    # Objeto 4: Stream de conteúdo
    offsets.append(sum(len(p) for p in parts))
    parts.append(
        f"4 0 obj\n<< /Length {length} >>\nstream\n".encode("latin-1")
        + stream_content
        + b"endstream\nendobj\n"
    )

    # Objeto 5: Fonte padrão Helvetica
    offsets.append(sum(len(p) for p in parts))
    parts.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    xref_offset = sum(len(p) for p in parts)
    parts.append(b"xref\n0 6\n0000000000 65535 f \n")
    for off in offsets:
        parts.append(f"{off:010d} 00000 n \n".encode("latin-1"))

    trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    parts.append(trailer.encode("latin-1"))

    return b"".join(parts)
