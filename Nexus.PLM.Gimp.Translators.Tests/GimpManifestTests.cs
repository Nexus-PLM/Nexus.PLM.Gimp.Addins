using Nexus.PLM.Addin.Sdk.Translators;
using Nexus.PLM.Addin.Sdk.Translators.Testing;
using Xunit;

namespace Nexus.PLM.Gimp.Translators.Tests;

/// <summary>
/// Contract tests for this repo's <c>translators/translators.json</c>: three xcf exports over
/// one script-fu script, format picked by the output extension.
/// </summary>
public class GimpManifestTests : ManifestContractTests
{
    /// <inheritdoc/>
    protected override string ManifestPath =>
        Path.Combine(AppContext.BaseDirectory, "translators", TranslatorManifest.FileName);

    /// <summary>The three keys reserved in the Services ownership table.</summary>
    [Fact]
    public void CarriesTheThreeReservedKeys() =>
        Assert.Equal(
            ["xcf_to_jpeg", "xcf_to_pdf", "xcf_to_png"],
            Load().Translators.Select(t => t.Key).OrderBy(k => k).ToArray());

    /// <summary>
    /// Paths travel through env vars, never inside the script-fu expression: a Windows path
    /// in a script-fu string literal is mangled by backslash escaping. Hold the exact shape.
    /// </summary>
    [Fact]
    public void EveryEntryCarriesPathsThroughEnvNotTheExpression()
    {
        foreach (var t in Load().Translators)
        {
            Assert.Equal("${ENV:GIMP_CMD}", t.Command);
            // --batch-interpreter is mandatory on GIMP 3.2: without it gimp-console prints the
            // interpreter list and idles forever instead of exiting (measured).
            Assert.Equal(
                ["-i", "--batch-interpreter", "plug-in-script-fu-eval", "-b", "(load (getenv \"GIMP_SCRIPT\"))"],
                t.Args);
            Assert.Equal("${dir}/xcf_export.scm", t.Env["GIMP_SCRIPT"]);
            Assert.Equal("${input}", t.Env["GIMP_INPUT"]);
            Assert.Equal("${output}", t.Env["GIMP_OUTPUT"]);
            Assert.Equal(".xcf", t.InputFileExtension);
            Assert.True(t.TimeoutSeconds >= 600, "GIMP's first headless start builds its font cache");
        }
    }

    /// <summary>The shared script sits beside the manifest, where <c>${dir}</c> resolves,
    /// and stays ASCII (console output goes through the system code page).</summary>
    [Fact]
    public void TheExportScriptSitsBesideTheManifest_AndIsAscii()
    {
        var script = Path.Combine(Path.GetDirectoryName(ManifestPath)!, "xcf_export.scm");

        Assert.True(File.Exists(script));
        var text = File.ReadAllText(script);
        Assert.False(text.Any(c => c > 127), "non-ASCII in the script");
        Assert.Contains("GIMP_INPUT", text);
        Assert.Contains("GIMP_OUTPUT", text);
        Assert.Contains("gimp-quit", text);
    }
}
