// Expo Constants 57.0.20 assumes iOS checkout paths contain no spaces.
// Apply the workaround after npm installs, before CocoaPods reads the podspec.
const fs = require("node:fs");
const path = require("node:path");
const packageRoot = path.dirname(
  require.resolve("expo-constants/package.json"),
);
function patch(relativePath, before, after) {
  const file = path.join(packageRoot, relativePath);
  const source = fs.readFileSync(file, "utf8");
  if (source.includes(after)) return;
  if (!source.includes(before)) {
    throw new Error(
      `Expo Constants changed: review the path workaround in ${relativePath}`,
    );
  }
  fs.writeFileSync(file, source.replace(before, after));
}
patch(
  "ios/EXConstants.podspec",
  "require 'json'",
  "require 'json'\nrequire 'shellwords'",
);
patch(
  "ios/EXConstants.podspec",
  "\"PROJECT_ROOT=#{ENV['PROJECT_ROOT']} \"",
  "\"PROJECT_ROOT=#{ENV['PROJECT_ROOT'].shellescape} \"",
);
patch(
  "ios/EXConstants.podspec",
  String.raw`:script => "bash -l -c \"#{env_vars}$PODS_TARGET_SRCROOT/../scripts/get-app-config-ios.sh\""`,
  String.raw`:script => "#{env_vars}bash -l \"$PODS_TARGET_SRCROOT/../scripts/get-app-config-ios.sh\""`,
);
patch(
  "scripts/get-app-config-ios.sh",
  "PROJECT_DIR_BASENAME=$(basename $PROJECT_DIR)",
  'PROJECT_DIR_BASENAME=$(basename "$PROJECT_DIR")',
);
console.log("Expo Constants iOS paths support spaces.");
