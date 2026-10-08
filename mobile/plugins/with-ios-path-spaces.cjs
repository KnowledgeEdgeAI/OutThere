const { withXcodeProject } = require("expo/config-plugins");

// The Expo template executes an unquoted command-substitution result.
// Quote the resolved script path so spaces in the checkout remain one argument.
module.exports = function withIosPathSpaces(config) {
  return withXcodeProject(config, (result) => {
    const phases =
      result.modResults.hash.project.objects.PBXShellScriptBuildPhase;
    for (const phase of Object.values(phases)) {
      if (typeof phase !== "object" || !phase.shellScript) continue;
      phase.shellScript = phase.shellScript.replace(
        /`([^`]*\/scripts\/react-native-xcode\.sh[^`]*)`/g,
        (_, command) => String.raw`\"$(${command})\"`,
      );
    }
    return result;
  });
};
