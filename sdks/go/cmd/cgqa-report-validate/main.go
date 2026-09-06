package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"

	interop "github.com/safal207/ContractGraph-QA/sdks/go"
)

func readInput() ([]byte, error) {
	if len(os.Args) > 2 {
		return nil, fmt.Errorf("usage: cgqa-report-validate [report.json]")
	}
	var reader io.Reader = os.Stdin
	if len(os.Args) == 2 {
		info, err := os.Lstat(os.Args[1])
		if err != nil {
			return nil, err
		}
		if info.Mode()&os.ModeSymlink != 0 || !info.Mode().IsRegular() {
			return nil, fmt.Errorf("input must be a non-symlink regular file")
		}
		file, err := os.Open(os.Args[1])
		if err != nil {
			return nil, err
		}
		defer file.Close()
		reader = file
	}
	raw, err := io.ReadAll(io.LimitReader(reader, interop.MaxReportBytes+1))
	if err != nil {
		return nil, err
	}
	if len(raw) > interop.MaxReportBytes {
		return nil, fmt.Errorf("input exceeds %d bytes", interop.MaxReportBytes)
	}
	return raw, nil
}

func main() {
	raw, err := readInput()
	if err == nil {
		var summary interop.Summary
		summary, err = interop.ValidateJSON(raw)
		if err == nil {
			err = json.NewEncoder(os.Stdout).Encode(summary)
		}
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "cgqa-report-validate:", err)
		os.Exit(2)
	}
}
