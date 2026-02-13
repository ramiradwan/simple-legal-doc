using System;
using System.Security.Cryptography;
using System.Threading.Tasks;

using Azure;
using Azure.Core;
using Azure.Identity;
using Azure.Developer.ArtifactSigning;
using Azure.Developer.ArtifactSigning.Models;

using iText.Signatures;

using Org.BouncyCastle.X509;

/// <summary>
/// Azure Trusted Signing adapter for iText.
/// 
/// Implements IExternalSignature:
/// - iText provides the hashable ByteRange
/// - We compute SHA-256
/// - We send the digest to Azure Trusted Signing
/// - We return a CMS-compatible signature
/// 
/// This class NEVER:
/// - Sees private keys
/// - Handles full PDFs
/// - Persists secrets
/// </summary>
public sealed class AzureTrustedSigner : IExternalSignature
{
    private readonly TrustedSigningClient _client;
    private readonly string _certificateProfile;
    private readonly X509Certificate[] _certificateChain;

    public AzureTrustedSigner()
    {
        // ---------------------------------------------------------------------
        // Environment configuration
        // ---------------------------------------------------------------------
        var accountName = Environment.GetEnvironmentVariable("AZURE_TRUSTED_SIGNING_ACCOUNT");
        var profileName = Environment.GetEnvironmentVariable("AZURE_TRUSTED_SIGNING_PROFILE");

        if (string.IsNullOrWhiteSpace(accountName))
            throw new InvalidOperationException("AZURE_TRUSTED_SIGNING_ACCOUNT is not set");

        if (string.IsNullOrWhiteSpace(profileName))
            throw new InvalidOperationException("AZURE_TRUSTED_SIGNING_PROFILE is not set");

        _certificateProfile = profileName;

        // ---------------------------------------------------------------------
        // Azure identity (Managed Identity or Service Principal)
        // ---------------------------------------------------------------------
        TokenCredential credential = new DefaultAzureCredential();

        _client = new TrustedSigningClient(
            new Uri($"https://{accountName}.trusted-signing.azure.net"),
            credential
        );

        // ---------------------------------------------------------------------
        // Load certificate chain (public only)
        // ---------------------------------------------------------------------
        // Note: Blocking call in constructor is acceptable for singleton service startup.
        // If this fails, the pod should crash (Fail Fast).
        _certificateChain = LoadCertificateChainAsync().GetAwaiter().GetResult();
    }

    // -------------------------------------------------------------------------
    // iText: algorithm identifiers
    // -------------------------------------------------------------------------

    public string GetHashAlgorithm() => DigestAlgorithms.SHA256;

    public string GetEncryptionAlgorithm() => "RSA";

    public X509Certificate[] CertificateChain => _certificateChain;

    // -------------------------------------------------------------------------
    // iText callback: sign message digest
    // -------------------------------------------------------------------------

    public byte[] Sign(byte[] message)
    {
        // iText passes the raw data that must be hashed
        byte[] digest;

        using (var sha256 = SHA256.Create())
        {
            digest = sha256.ComputeHash(message);
        }

        // Azure Trusted Signing call (sync wrapper is required by iText)
        return SignDigestAsync(digest).GetAwaiter().GetResult();
    }

    // -------------------------------------------------------------------------
    // Azure Trusted Signing invocation
    // -------------------------------------------------------------------------

    private async Task<byte[]> SignDigestAsync(byte[] digest)
    {
        var request = new SignRequest(
            certificateProfileName: _certificateProfile,
            signingAlgorithm: SigningAlgorithm.RsaPkcs1Sha256,
            digest: digest
        );

        Response<SignResponse> response;

        try
        {
            response = await _client.SignAsync(request);
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException(
                $"Azure Trusted Signing failed: {ex.Message}",
                ex
            );
        }

        return response.Value.Signature;
    }

    // -------------------------------------------------------------------------
    // Certificate chain retrieval (public material only)
    // -------------------------------------------------------------------------

    private async Task<X509Certificate[]> LoadCertificateChainAsync()
    {
        Response<GetCertificateChainResponse> response;

        try
        {
            response = await _client.GetCertificateChainAsync(_certificateProfile);
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException(
                $"Failed to retrieve certificate chain: {ex.Message}",
                ex
            );
        }

        var chain = response.Value.Certificates;
        var result = new X509Certificate[chain.Count];

        for (int i = 0; i < chain.Count; i++)
        {
            result[i] = new X509Certificate(chain[i].RawData);
        }

        return result;
    }
}