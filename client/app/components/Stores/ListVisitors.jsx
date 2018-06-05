import React from 'react';
import {Col, Row, Panel, Alert} from 'react-bootstrap';
import {withRouter, Link} from "react-router-dom";
import {Stomp} from 'stompjs/lib/stomp.min';
import axios from "axios/index";
import _ from 'underscore';

class ListVisitors extends React.Component {
    constructor(props) {
        super(props);

        this.state = {};
    }

    /**
     * This function is used to load the relist of visitors
     */
    reloadVisitorList()
    {
        axios({
            method: 'get',
            url: `/store/${this.props.store._id}/visitors/`
        }).then((response) =>
        {
            const state = {visitors: response.data};
            if (this.props.match && this.props.match.params && this.props.match.params.visitorId)
            {
                state.visitor =_.findWhere(state.visitors, {visitorId: this.props.match.params.visitorId});
            }
            this.setState(state);
        });
    }


    /**
     * Triggered when this component appears on the screen.
     */
    componentDidMount()
    {
        this.reloadVisitorList();
        this.updateInterval = setInterval(() => this.reloadVisitorList(), 2500);
    }


    /**
     * Triggered when this component is being removed from the screen
     */
    componentWillUnmount()
    {
        if (this.updateInterval)
        {
            clearInterval(this.updateInterval);
        }
    }

    render() {
        return (
            <div className="store-cameras">
                <br/>
                <Row>
                    <Col md={3}>
                        <div className="panel b">
                            <div className="panel-body">
                                <strong className="text-muted">Recent Visitors</strong>
                            </div>
                            <div className="list-group">
                                {
                                    this.state.visitors &&
                                    this.state.visitors.map((visitor) =>
                                        <Link key={visitor.visitorId} to={"/store/" + this.props.store._id + "/visitor/" + visitor.visitorId}
                                              className={"list-group-item " + (this.state.visitor && visitor.visitorId === this.state.visitor.visitorId ? " active" : "")}>
                                            <span>{visitor.visitorId}</span>
                                        </Link>
                                    )
                                }
                            </div>
                        </div>
                    </Col>
                    {this.state.visitor &&
                    <Col md={9}>
                        <div className="row">
                            <h1>{this.state.visitor.visitorId}</h1>
                        </div>
                    </Col>
                    }
                </Row>
            </div>
        );
    }
}

export default withRouter(ListVisitors);


