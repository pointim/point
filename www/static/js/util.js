if (!String.prototype.trim) {
    String.prototype.trim = function(){
        return this.replace(/^\s+|\s+$/, '');
    };
}

Number.prototype.strftime = function(fmt){
    var d  = new Date(this*1000);
    return d.strftime(fmt);
};
