export class FomodChoicesRequiredError extends Error {
    code;
    details;
    constructor(args) {
        super(args.message);
        this.name = "FomodChoicesRequiredError";
        this.code = args.code;
        this.details = { fomod_tree: args.fomod_tree };
    }
}
