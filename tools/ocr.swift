// Read the caption printed on a plate, using macOS's own Vision OCR.
//
// Broinowski's plates carry their species names in type along the foot -
// "ANAS SUPERCILIOSA (Gmel) / Australian Wild Duck" - which is the only
// practical way to identify the ~440 of them whose Commons descriptions are
// Internet Archive OCR noise.
//
// Swift rather than Python because Vision is already on the machine: pyobjc
// will not build against this Python, and tesseract would be a system install
// for something macOS ships.
//
//   swift tools/ocr.swift strip1.png strip2.png ...
//   -> one tab-separated line per file: path <TAB> text | text | text
//
// Language correction is off deliberately. It "fixes" scientific names into
// English words, which is precisely the wrong behaviour here.

import Foundation
import Vision
import AppKit

for path in CommandLine.arguments.dropFirst() {
    guard let image = NSImage(contentsOfFile: path),
          let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        print("\(path)\tERROR: unreadable")
        continue
    }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["en-US"]

    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    do { try handler.perform([request]) }
    catch { print("\(path)\tERROR: \(error)"); continue }

    let lines = (request.results ?? []).compactMap {
        $0.topCandidates(1).first?.string
    }
    print("\(path)\t\(lines.joined(separator: " | "))")
}
