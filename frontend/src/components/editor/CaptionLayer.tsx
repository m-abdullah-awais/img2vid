"use client";

import { memo, type CSSProperties } from "react";
import { CAPTION_FONT, captionGeometry, captionText } from "@/lib/captions";
import type { CaptionSettings } from "@/lib/types";

type Props = {
  /** The line on screen. A line with no words shows nothing, as in the build. */
  text: string;
  settings: CaptionSettings;
  /** The build size, "1920x1080", which every length is a fraction of. */
  size: string;
};

/**
 * The words of the line on screen, drawn where the build will burn them.
 *
 * Every length is a share of the frame, so this holds at any stage size and
 * for a vertical project: the layer is its own size container and the shares
 * are written in cqw and cqh. A container of its own, rather than the stage
 * itself, because the stage sizes itself in the viewing well's container
 * units and a second use of those units on the same element reads badly.
 *
 * The outline is two spans in one grid cell rather than a stroke over the
 * fill: libass grows its outline outwards from the letter, and a stroke
 * centred on the letter would eat a pixel out of every stem. The band is one
 * inline span, so each wrapped line gets its own box exactly as libass draws
 * it, and its padding overflows the line the same way.
 */
export const CaptionLayer = memo(function CaptionLayer({ text, settings, size }: Props) {
  const words = captionText(text);
  if (!settings.on || !words) return null;

  const frame = captionGeometry(size, settings);
  const middle = settings.place === "middle";
  const box: CSSProperties = {
    left: `${frame.side * 100}cqw`,
    right: `${frame.side * 100}cqw`,
    ...(middle
      ? { top: 0, bottom: 0 }
      : settings.place === "top"
        ? { top: `${frame.margin * 100}cqh` }
        : { bottom: `${frame.margin * 100}cqh` }),
  };
  const type: CSSProperties = {
    fontFamily: CAPTION_FONT,
    fontSize: `${frame.font * 100}cqh`,
    lineHeight: frame.lineHeight,
    // libass rebalances its lines for this wrap style, and measuring says so:
    // on a 9:16 build the widest line came out 8 percent of the frame wider
    // than the video with plain greedy wrapping, and within 1 percent of it
    // with this. The words can still fall differently between the two.
    textWrap: "balance",
  };
  // Twice the outline, because half of a stroke sits inside the letter and
  // is covered by the white on top of it.
  const stroke: CSSProperties = {
    WebkitTextStrokeWidth: `${frame.outline * 200}cqh`,
    WebkitTextStrokeColor: "#000",
    color: "#000",
  };
  const band: CSSProperties = {
    backgroundColor: "#000",
    padding: `${frame.outline * 100}cqh`,
    WebkitBoxDecorationBreak: "clone",
    boxDecorationBreak: "clone",
  };

  return (
    <div
      aria-hidden
      data-captions={settings.place}
      className="pointer-events-none absolute inset-0 select-none"
      style={{ containerType: "size" }}
    >
      <div
        className={`absolute flex justify-center ${middle ? "items-center" : ""}`}
        style={box}
      >
        <p className="grid w-full text-center text-[#fff]" style={type}>
          {settings.look === "band" ? (
            <span className="col-start-1 row-start-1">
              <span style={band}>{words}</span>
            </span>
          ) : (
            <>
              <span className="col-start-1 row-start-1" style={stroke}>
                {words}
              </span>
              <span className="col-start-1 row-start-1">{words}</span>
            </>
          )}
        </p>
      </div>
    </div>
  );
});
