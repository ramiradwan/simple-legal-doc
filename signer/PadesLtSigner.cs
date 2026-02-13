using System;
using System.IO;
using System.Threading.Tasks;
using System.Collections.Generic;

using iText.Kernel.Pdf;
using iText.Signatures;

public sealed class PadesLtSigner
{
    private readonly AzureTrustedSigner _externalSigner;

    // Microsoft's public timestamping service (free, reliable)
    private const string TsaUrl = "http://timestamp.acs.microsoft.com";

    public PadesLtSigner(AzureTrustedSigner externalSigner)
    {
        _externalSigner = externalSigner;
    }

    /// <summary>
    /// Applies an incremental PAdES-B-LT signature to a finalized PDF/A-3b document.
    /// 
    /// Contract:
    /// - Input MUST already be PDF/A-3b
    /// - Document content, attachments, and metadata are preserved
    /// - Output is append-only (incremental update)
    /// </summary>
    public async Task<byte[]> SignAsync(Stream inputPdf)
    {
        if (inputPdf is null)
            throw new ArgumentNullException(nameof(inputPdf));

        // Output buffer (no filesystem writes)
        await using var output = new MemoryStream();

        // ---------------------------------------------------------------------
        // PDF reader & signer (incremental / append mode)
        // ---------------------------------------------------------------------
        // StampingProperties.UseAppendMode() is CRITICAL for PDF/A preservation.
        using var reader = new PdfReader(inputPdf);
        var signer = new PdfSigner(
            reader,
            output,
            new StampingProperties().UseAppendMode()
        );

        // ---------------------------------------------------------------------
        // Signature appearance (minimal, non-visual)
        // ---------------------------------------------------------------------
        // We set a semantic reason but avoid strict visual locking since
        // the upstream engine handles the visual "seal" rendering.
        var appearance = signer.GetSignatureAppearance()
            .SetReason("Document issued by simple-legal-doc")
            .SetLocation("Automated document service");

        signer.SetFieldName("Signature1");

        // ---------------------------------------------------------------------
        // PAdES baseline configuration
        // ---------------------------------------------------------------------
        IExternalSignature externalSignature = _externalSigner;
        IExternalDigest digest = new BouncyCastleDigest();

        // ---------------------------------------------------------------------
        // LTV Configuration: OCSP + CRL + TSA
        // ---------------------------------------------------------------------
        // 1. OCSP (Online Certificate Status Protocol)
        var ocspClient = new OcspClientBouncyCastle(null);
        
        // 2. CRL (Certificate Revocation List)
        var crlClient = new CrlClientOnline();

        // 3. TSA (Timestamp Authority) - CRITICAL FIX
        // This freezes the signature validity in time, allowing LTV (Long-Term Validation).
        ITSAClient tsaClient = new TSAClientBouncyCastle(TsaUrl, null, null);

        // ---------------------------------------------------------------------
        // Perform detached signature (incremental)
        // ---------------------------------------------------------------------
        // Note: We use CADES standard which is the underlying format for PAdES
        signer.SignDetached(
            digest,
            externalSignature,
            _externalSigner.CertificateChain,
            new[] { crlClient }, // Fetch CRLs online
            ocspClient,          // Fetch OCSP online
            tsaClient,           // <--- ADDED: Apply Trusted Timestamp
            0,                   // Estimated size (0 = let iText calculate)
            PdfSigner.CryptoStandard.CADES
        );

        return output.ToArray();
    }
}