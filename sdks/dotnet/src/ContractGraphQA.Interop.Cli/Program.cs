using System.Text.Json;
using ContractGraphQA.Interop;

try
{
    if (args.Length > 1) throw new IOException("usage: cgqa-report-validate [report.json]");
    await using Stream input = args.Length == 0 ? Console.OpenStandardInput() : OpenRegularFile(args[0]);
    byte[] raw = await ReadBounded(input);
    var summary = InteropReportValidator.Validate(raw);
    Console.WriteLine(JsonSerializer.Serialize(summary, new JsonSerializerOptions(JsonSerializerDefaults.Web)));
    return 0;
}
catch (Exception exception)
{
    Console.Error.WriteLine("cgqa-report-validate: " + exception.Message);
    return 2;
}

static FileStream OpenRegularFile(string name)
{
    var file = new FileInfo(name);
    if (!file.Exists || file.LinkTarget is not null || (file.Attributes & FileAttributes.Directory) != 0)
        throw new IOException("input must be a non-symlink regular file");
    if (file.Length > InteropReportValidator.MaxReportBytes) throw new IOException("input is too large");
    return file.OpenRead();
}

static async Task<byte[]> ReadBounded(Stream stream)
{
    var buffer = new byte[InteropReportValidator.MaxReportBytes + 1];
    int offset = 0;
    while (offset < buffer.Length)
    {
        int read = await stream.ReadAsync(buffer.AsMemory(offset, buffer.Length - offset));
        if (read == 0) break;
        offset += read;
    }
    if (offset > InteropReportValidator.MaxReportBytes) throw new IOException("input is too large");
    return buffer[..offset];
}
