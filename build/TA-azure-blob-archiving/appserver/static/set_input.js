require(["jquery", "splunkjs/mvc/simplexml/ready!"], function($) {

    $("[id^=date_start]")
            .find("input")
            .attr('type','date')

    $("[id^=date_end]")
            .find("input")
            .attr('type','date')

});