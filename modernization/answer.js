// Copyright (c) OpenAI. All rights reserved.
const path = require("path");
const fs = require("fs");
const { imageSize } = require("image-size");
const pptxgen = require("pptxgenjs");
const { icon } = require("@fortawesome/fontawesome-svg-core");
const { faHammer } = require("@fortawesome/free-solid-svg-icons");
// These are the constants for slides_template.js, adapt them to your content accordingly.
// To read the rest of the template, see slides_template.js.
const SLIDE_HEIGHT = 5.625; // inches
const SLIDE_WIDTH = (SLIDE_HEIGHT / 9) * 16; // 10 inches
const BULLET_INDENT = 15; // USE THIS FOR BULLET INDENTATION SPACINGS. Example: {text: "Lorem ipsum dolor sit amet.",options: { bullet: { indent: BULLET_INDENT } },},
const FONT_FACE = "Arial";
const FONT_SIZE = {
  PRESENTATION_TITLE: 36,
  PRESENTATION_SUBTITLE: 12,
  SLIDE_TITLE: 24,
  DATE: 12,
  SECTION_TITLE: 16,
  TEXT: 12,
  DETAIL: 8,
  PLACEHOLDER: 10,
  CITATION: 6,
  SUBHEADER: 21,
};
const CITATION_HEIGHT = calcTextBoxHeight(FONT_SIZE.CITATION);
const MARGINS = {
  DEFAULT_PADDING_BOTTOM: 0.23,
  DEFAULT_CITATION: SLIDE_HEIGHT - CITATION_HEIGHT - 0.15,
  ELEMENT_MEDIUM_PADDING_MEDIUM: 0.3,
  ELEMENT_MEDIUM_PADDING_LARGE: 0.6,
};
const SLIDE_TITLE = { X: 0.3, Y: 0.3, W: "94%" };
const WHITE = "FFFFFF"; // FOR BACKGROUND, adapt as needed for a light theme.
const BLACK = "000000"; // ONLY FOR FONTS, ICONS, ETC, adapt as needed for a light theme
const NEAR_BLACK_NAVY = "030A18"; // ONLY FOR FONTS, ICONS, ETC, adapt as needed for a light theme
const LIGHT_GRAY = "f5f5f5";
const GREYISH_BLUE = "97B1DF"; // FOR OTHER HIGHLIGHTS, adapt as needed for a light theme
const LIGHT_GREEN = "A4B6B8"; // FOR ICONS AND HIGHLIGHTS, adapt as needed for a light theme
// Just a placeholder! If you see slide using this, you'll need to replace it with actual assets—either generated or sourced from the internet.
const PLACEHOLDER_LIGHT_GRAY_BLOCK = path.join(
  __dirname,
  "placeholder_light_gray_block.png"
);
const imageInfoCache = new Map();
/**
 * Calculate the height of a text box in inches.
 * @param {number} fontSize Font size in points.
 * @param {number} [lines=1] Number of lines.
 * @param {number} [leading=1.2] Leading multiplier.
 * @param {number} [padding=0.15] Padding in inches.
 * @returns {number} Height in inches.
 */
function calcTextBoxHeight(fontSize, lines = 1, leading = 1.2, padding = 0.15) {
  const lineHeightIn = (fontSize / 72) * leading;
  return lines * lineHeightIn + padding;
}
/**
 * Return basic dimension information for the image at the given path.
 * @param {string} path Local file path to the image.
 * @returns {{width: number, height: number, aspectRatio: number}}
 */
function getImageDimensions(path) {
  if (imageInfoCache.has(path)) return imageInfoCache.get(path);
  const dimensions = imageSize(fs.readFileSync(path));
  imageInfoCache.set(path, {
    width: dimensions.width,
    height: dimensions.height,
    aspectRatio: dimensions.width / dimensions.height,
  });
  return imageInfoCache.get(path);
}
/**
 * Calculate a bounding box that contains the image without cropping.
 * @param {string} path Local file path to the image.
 * @param {number} x X coordinate (in inches) of the bounding box.
 * @param {number} y Y coordinate (in inches) of the bounding box.
 * @param {number} w Width of the bounding box in inches.
 * @param {number} h Height of the bounding box in inches.
 * @returns {{x: number, y: number, w: number, h: number}}
 */
function imageSizingContain(path, x, y, w, h) {
  // path: local file path; x, y, w, h: viewport inches
  const { aspectRatio } = getImageDimensions(path),
    boxAspect = w / h;
  const w2 = aspectRatio >= boxAspect ? w : h * aspectRatio,
    h2 = aspectRatio >= boxAspect ? w2 / aspectRatio : h;
  return { x: x + (w - w2) / 2, y: y + (h - h2) / 2, w: w2, h: h2 };
}
/**
 * Calculate a virtual canvas size and cropping parameters for an image to fill a box.
 * @param {string} path Local file path to the image.
 * @param {number} x X coordinate (in inches) of the bounding box.
 * @param {number} y Y coordinate (in inches) of the bounding box.
 * @param {number} w Width of the bounding box in inches.
 * @param {number} h Height of the bounding box in inches.
 * @returns {{x: number, y: number, w: number, h: number, sizing: {type: string, x: number, y: number, w: number, h: number}}}
 */
function imageSizingCrop(path, x, y, w, h) {
  // path: local file path; x, y, w, h: viewport inches
  const { aspectRatio } = getImageDimensions(path),
    boxAspect = w / h;
  let cx, cy, cw, ch;
  if (aspectRatio >= boxAspect) {
    cw = boxAspect / aspectRatio;
    ch = 1;
    cx = (1 - cw) / 2;
    cy = 0;
  } else {
    cw = 1;
    ch = aspectRatio / boxAspect;
    cx = 0;
    cy = (1 - ch) / 2;
  }
  let virtualW = w / cw,
    virtualH = virtualW / aspectRatio,
    eps = 1e-6;
  if (Math.abs(virtualH * ch - h) > eps) {
    virtualH = h / ch;
    virtualW = virtualH * aspectRatio;
  }
  return {
    x,
    y,
    w: virtualW,
    h: virtualH,
    sizing: { type: "crop", x: cx * virtualW, y: cy * virtualH, w, h },
  };
}
const hSlideTitle = calcTextBoxHeight(FONT_SIZE.SLIDE_TITLE);
/**
 * Add a title text box to a slide.
 * @param {import('pptxgenjs').Slide} slide Slide instance.
 * @param {string} title Title text.
 * @param {string} [color] Hex string for font colour.
 * @returns {void}
 */
function addSlideTitle(slide, title, color = BLACK) {
  slide.addText(title, {
    x: SLIDE_TITLE.X,
    y: SLIDE_TITLE.Y,
    w: SLIDE_TITLE.W,
    h: hSlideTitle,
    fontFace: FONT_FACE,
    fontSize: FONT_SIZE.SLIDE_TITLE,
    color,
  });
}
/**
 * Convert a FontAwesome icon definition to an SVG string.
 * @param {object} faIcon FontAwesome icon definition.
 * @param {string} color Hex colour for the icon.
 * @returns {string} SVG string.
 */
function getIconSvg(faIcon, color) {
  // CSS color, syntax slightly different from pptxgenjs.
  return icon(faIcon, { styles: { color: `#${color}` } }).html.join("");
}
/**
 * Convert an SVG string to a data URI.
 * @param {string} svg SVG content.
 * @returns {string} Data URI encoding of the SVG.
 */
const svgToDataUri = (svg) =>
  "data:image/svg+xml;base64," + Buffer.from(svg).toString("base64");
 (async () => {
  const pptx = new pptxgen();
  pptx.defineLayout({ name: "16x9", width: SLIDE_WIDTH, height: SLIDE_HEIGHT });
  pptx.layout = "16x9";
  // Slide 1: Title slide with subtitle and date.
  {
    const slide = pptx.addSlide();
    slide.addImage({
      path: PLACEHOLDER_LIGHT_GRAY_BLOCK,
      ...imageSizingCrop(
        PLACEHOLDER_LIGHT_GRAY_BLOCK,
        0.55 * SLIDE_WIDTH,
        0.1 * SLIDE_HEIGHT,
        0.45 * SLIDE_WIDTH,
        0.8 * SLIDE_HEIGHT
      ),
    });
    const leftMargin = 0.3;
    const hTitle = calcTextBoxHeight(FONT_SIZE.PRESENTATION_TITLE);
    slide.addText("Presentation title", {
      fontFace: FONT_FACE,
      fontSize: FONT_SIZE.PRESENTATION_TITLE,
      x: leftMargin,
      y: (SLIDE_HEIGHT - hTitle) / 2,
      w: "50%",
      h: calcTextBoxHeight(FONT_SIZE.PRESENTATION_TITLE),
      valign: "middle",
    });
    slide.addText("Subtitle here", {
      fontFace: FONT_FACE,
      fontSize: FONT_SIZE.PRESENTATION_SUBTITLE,
      x: leftMargin,
      y: 3.15,
      w: "50%",
      h: calcTextBoxHeight(FONT_SIZE.PRESENTATION_SUBTITLE),
    });
    let hDate = calcTextBoxHeight(FONT_SIZE.DATE);
    slide.addText("Date here", {
      fontFace: FONT_FACE,
      fontSize: FONT_SIZE.DATE,
      x: leftMargin,
      y: SLIDE_HEIGHT - 0.375 - hDate,
      w: 3.75,
      h: hDate,
    });
  }
  // Add more slides here by referring to slides_template.js for the code template.
  await pptx.writeFile({ fileName: "answer.pptx" });
})();
