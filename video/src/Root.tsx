import { Composition } from "remotion";
import { Deck, DeckProps } from "./Deck";
import { Launch, LaunchProps } from "./Launch";

const sample: DeckProps = { fps: 30, slides: [{ kind: "title", title: "Sample", frames: 90, captions: [] }] };
export const Root = () => (<>
  <Composition id="Launch" component={Launch} width={1920} height={1080} fps={30} durationInFrames={300} defaultProps={{ scenes: [{ type: "intro", frames: 300 }], music: "music.mp3", duck: [] } as LaunchProps}
    calculateMetadata={({ props }: { props: LaunchProps }) => ({ durationInFrames: Math.max(1, props.scenes.reduce((a, s) => a + s.frames, 0)) })} />
  <Composition id="Deck" component={Deck} width={1920} height={1080} fps={30} durationInFrames={90} defaultProps={sample}
    calculateMetadata={({ props }: { props: DeckProps }) => ({ durationInFrames: Math.max(1, props.slides.reduce((a, s) => a + s.frames, 0)), fps: props.fps })} />
</>);
