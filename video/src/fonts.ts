import { loadFont } from "@remotion/google-fonts/Inter";

// Inter (SIL Open Font License), with Vietnamese and Latin extended for accents.
export const { fontFamily } = loadFont("normal", {
  weights: ["600", "800"],
  subsets: ["latin", "latin-ext", "vietnamese"],
});
