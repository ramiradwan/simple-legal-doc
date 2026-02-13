using Microsoft.AspNetCore.Http;  
using Microsoft.AspNetCore.Routing;  
  
public static class SignEndpoint  
{  
    private const long MaxPdfSizeBytes = 25 * 1024 * 1024; // 25 MB  
  
    public static void Map(IEndpointRouteBuilder app)  
    {  
        app.MapPost("/sign-archival", HandleAsync)  
           .DisableAntiforgery(); // explicit: this is not a browser endpoint  
    }  
  
    private static async Task<IResult> HandleAsync(  
        HttpRequest request,  
        PadesLtSigner signer  
    )  
    {  
        // ---------------------------------------------------------------------  
        // Content-type enforcement  
        // ---------------------------------------------------------------------  
        if (!request.HasFormContentType)  
        {  
            return Results.BadRequest("Expected multipart/form-data");  
        }  
  
        var form = await request.ReadFormAsync();  
        var file = form.Files.GetFile("file");  
  
        if (file is null)  
        {  
            return Results.BadRequest("Missing 'file' field");  
        }  
  
        // ---------------------------------------------------------------------  
        // Size enforcement (defense-in-depth)  
        // ---------------------------------------------------------------------  
        if (file.Length <= 0)  
        {  
            return Results.BadRequest("Empty file");  
        }  
  
        if (file.Length > MaxPdfSizeBytes)  
        {  
            return Results.BadRequest("PDF exceeds maximum allowed size");  
        }  
  
        // ---------------------------------------------------------------------  
        // Media type enforcement  
        // ---------------------------------------------------------------------  
        if (!string.Equals(file.ContentType, "application/pdf", StringComparison.OrdinalIgnoreCase))  
        {  
            return Results.BadRequest("Only application/pdf is supported");  
        }  
  
        await using var inputStream = file.OpenReadStream();  
  
        byte[] signedPdf;  
  
        try  
        {  
            signedPdf = await signer.SignAsync(inputStream);  
        }  
        catch  
        {  
            // Intentionally opaque — do not leak signing internals  
            return Results.Problem(  
                title: "Signing failed",  
                statusCode: StatusCodes.Status500InternalServerError  
            );  
        }  
  
        // ---------------------------------------------------------------------  
        // Response  
        // ---------------------------------------------------------------------  
        return Results.File(  
            signedPdf,  
            contentType: "application/pdf",  
            fileDownloadName: "document_signed.pdf"  
        );  
    }  
}  