using Microsoft.AspNetCore.Builder;  
using Microsoft.AspNetCore.Http.Features;  
using Microsoft.Extensions.DependencyInjection;  
using Microsoft.Extensions.Hosting;  
  
var builder = WebApplication.CreateBuilder(args);  
  
// -----------------------------------------------------------------------------  
// Services  
// -----------------------------------------------------------------------------  
  
builder.Services.Configure<FormOptions>(options =>  
{  
    options.MultipartBodyLengthLimit = 25 * 1024 * 1024;  
});  
  
builder.Services.AddSingleton<PadesLtSigner>();  
builder.Services.AddSingleton<AzureTrustedSigner>();  
  
var app = builder.Build();  
  
// -----------------------------------------------------------------------------  
// Pipeline  
// -----------------------------------------------------------------------------  
  
app.UseRouting();  
  
// -----------------------------------------------------------------------------  
// Endpoints  
// -----------------------------------------------------------------------------  
  
SignEndpoint.Map(app);  
  
app.MapGet("/healthz", () => Results.Ok("ok"));  
  
app.Run();  