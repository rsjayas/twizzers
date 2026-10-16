import { Composition } from "remotion";
import { PoemVideo } from "./PoemVideo.jsx";
import { FPS, durationInSeconds } from "./timing.js";

const defaultProps = {
  poem: "Roses are red,\nViolets are blue,\nThis is a sample poem\nJust for you.",
  recipient: "",
  moodTags: ["romantic"],
  musicUrl: null,
};

export const Root = () => (
  <Composition
    id="PoemVideo"
    component={PoemVideo}
    width={1080}
    height={1920}
    fps={FPS}
    durationInFrames={Math.round(durationInSeconds(defaultProps.poem) * FPS)}
    defaultProps={defaultProps}
    calculateMetadata={({ props }) => ({
      durationInFrames: Math.round(durationInSeconds(props.poem) * FPS),
    })}
  />
);
